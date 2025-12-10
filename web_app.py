from flask import Flask, render_template, request, Response
import core_logic
import reminder_utils
from datetime import datetime, timedelta
from icalendar import Calendar, Event, Alarm
import json
import pytz

app = Flask(__name__)

@app.route('/export', methods=['POST'])
def export_calendar():
    matches = request.form.getlist('matches')
    if not matches:
        return "No matches selected", 400
    
    cal = Calendar()
    cal.add('prodid', '-//Kanqiu v3//mxm.dk//')
    cal.add('version', '2.0')
    
    # Assume Beijing Time
    tz = pytz.timezone('Asia/Shanghai')

    for match_json in matches:
        try:
            m = json.loads(match_json.replace("'", '"'))
            
            # Parse match time
            start_time = datetime.strptime(m['time'], "%Y-%m-%d %H:%M")
            start_time = tz.localize(start_time)
            
            # End time (approx 2 hours)
            end_time = start_time + timedelta(hours=2)
            
            event = Event()
            summary = f"{m['team']} vs {m['opponent']}"
            event.add('summary', summary)
            event.add('dtstart', start_time)
            event.add('dtend', end_time)
            event.add('description', f"{m['competition']} - {m['home_away']}")
            event.add('location', m['home_away'])
            
            # Calculate Reminder Time
            # reminder_utils.calculate_reminder_time returns string "%Y-%m-%d %H:%M"
            remind_str = reminder_utils.calculate_reminder_time(m['time'])
            remind_dt = datetime.strptime(remind_str, "%Y-%m-%d %H:%M")
            remind_dt = tz.localize(remind_dt)
            
            # STRATEGY: Handle Delayed Reminders (e.g. 4am match, 7am reminder)
            # Mobile calendars often FAIL to support POSITIVE triggers (After Start).
            # They treat all triggers as negative (Before Start).
            # SOLUTION: If reminder is AFTER start, create a SEPARATE event.
            
            if remind_dt > start_time:
                # Case 1: Delayed Reminder (Separate Event)
                
                # 1.1 Add the Match Event (No Alarm)
                # We don't add an alarm to the match itself to avoid confusion/wrong alerts
                cal.add_component(event)
                
                # 1.2 Add the Reminder Event
                remind_event = Event()
                remind_summary = f"⏰ 赛果: {summary}"
                remind_event.add('summary', remind_summary)
                remind_event.add('dtstart', remind_dt)
                remind_event.add('dtend', remind_dt + timedelta(minutes=15)) # Short duration
                remind_event.add('description', f"查看比分: {m['competition']}")
                
                # Add an immediate alarm to this reminder event
                alarm = Alarm()
                alarm.add('action', 'DISPLAY')
                alarm.add('description', f"Check Score: {summary}")
                alarm.add('trigger', timedelta(minutes=0)) # Trigger at start of reminder event
                
                remind_event.add_component(alarm)
                cal.add_component(remind_event)
                
            else:
                # Case 2: Standard Reminder (Before Start)
                # Calculate duration (should be negative, e.g. -30 mins)
                trigger_duration = remind_dt - start_time
                
                alarm = Alarm()
                alarm.add('action', 'DISPLAY')
                alarm.add('description', f"Reminder: {summary}")
                alarm.add('trigger', trigger_duration)
                
                event.add_component(alarm)
                cal.add_component(event)
        except Exception as e:
            print(f"Error parsing match: {e}")
            continue
    
    return Response(
        cal.to_ical(),
        mimetype='text/calendar',
        headers={"Content-disposition": "attachment; filename=fixtures.ics"}
    )

@app.route('/', methods=['GET', 'POST'])
def index():
    teams = ["All"] + list(core_logic.TEAMS.keys())
    selected_team = "All"
    fixtures = []
    error = None
    
    if request.method == 'POST':
        selected_team = request.form.get('team')
        try:
            fixtures = core_logic.get_formatted_fixtures(selected_team)
        except Exception as e:
            error = str(e)
            
    return render_template('index.html', teams=teams, selected_team=selected_team, fixtures=fixtures, error=error)

if __name__ == '__main__':
    print("Starting Web Interface...")
    # Get local IP for convenience
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        print(f" > Local Access: http://127.0.0.1:5000")
        print(f" > Network Access: http://{local_ip}:5000 (Use this on mobile)")
    except:
        print(" > Could not determine local IP")
        
    app.run(debug=True, host='0.0.0.0', port=5000)
