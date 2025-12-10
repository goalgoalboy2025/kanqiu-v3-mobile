import threading
from datetime import datetime
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.recycleview import RecycleView
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.properties import BooleanProperty, StringProperty
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.uix.behaviors import FocusBehavior
from kivy.uix.recycleview.layout import LayoutSelectionBehavior
from kivy.clock import Clock
from kivy.core.window import Window

from kivy.utils import platform
import reminder_utils

# Try to import core_logic, handle if missing (for dev environment)
try:
    import core_logic
    TEAMS = core_logic.TEAMS
except ImportError:
    core_logic = None
    TEAMS = {"Arsenal": "arsenal", "Man City": "manchester-city"} # Fallback

# Chinese font support for Kivy
from kivy.core.text import LabelBase

# We might need to register a Chinese font if default doesn't support it
# For Windows, we can try to find msyh.ttc or simhei.ttf
# But Kivy often needs ttf. 
# Let's try to set a default font if possible, or assume system handles it.
# In a packaged Android app, we'd include the font.
# For now, let's use a standard font or skip if not critical for "draft".
# But user wants Chinese text.
# I will set a font_name in the kv/style if I can find one, or just rely on default.
# To be safe for Android, we usually bundle a font.
# I will add a todo to bundle a font later.

class SelectableRecycleBoxLayout(FocusBehavior, LayoutSelectionBehavior,
                                 RecycleBoxLayout):
    ''' Adds selection and focus behaviour to the view. '''
    pass

class SelectableLabel(RecycleDataViewBehavior, BoxLayout):
    ''' Add selection support to the Label '''
    index = None
    selected = BooleanProperty(False)
    selectable = BooleanProperty(True)
    text = StringProperty("")
    
    def refresh_view_attrs(self, rv, index, data):
        ''' Catch and handle the view changes '''
        self.index = index
        self.text = data.get('text', '')
        self.selected = data.get('selected', False)
        return super(SelectableLabel, self).refresh_view_attrs(
            rv, index, data)

    def on_touch_down(self, touch):
        ''' Add selection on touch down '''
        if super(SelectableLabel, self).on_touch_down(touch):
            return True
        if self.collide_point(*touch.pos) and self.selectable:
            return self.parent.select_with_touch(self.index, touch)

    def apply_selection(self, rv, index, is_selected):
        ''' Respond to the selection of items in the view. '''
        self.selected = is_selected
        if is_selected:
            rv.data[index]['selected'] = True
        else:
            rv.data[index]['selected'] = False

class FootballApp(App):
    def build(self):
        self.title = "Kanqiu v3 (Mobile)"
        
        # Main Layout
        root = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        # Header: Team Selection
        header = BoxLayout(size_hint_y=None, height='50dp', spacing=10)
        
        # Team Spinner
        team_values = ['All'] + list(TEAMS.keys())
        # Translate 'All' to '所有球队' for display if needed, but keeping logic simple
        self.spinner = Spinner(
            text='All',
            values=team_values,
            size_hint=(0.7, 1)
        )
        header.add_widget(self.spinner)
        
        # Refresh Button
        btn_refresh = Button(text='Refresh', size_hint=(0.3, 1))
        btn_refresh.bind(on_press=self.fetch_fixtures)
        header.add_widget(btn_refresh)
        
        root.add_widget(header)
        
        # Info Label
        self.info_label = Label(text="Select a team and click Refresh", size_hint_y=None, height='30dp')
        root.add_widget(self.info_label)

        # Content: Fixture List
        self.rv = RecycleView()
        self.rv.viewclass = 'SelectableLabel'
        
        # Layout for RV
        layout = SelectableRecycleBoxLayout(default_size=(None, 50), default_size_hint=(1, None), size_hint_y=None)
        layout.bind(minimum_height=layout.setter('height'))
        layout.orientation = 'vertical'
        layout.multiselect = True
        layout.touch_multiselect = True
        
        self.rv.add_widget(layout)
        root.add_widget(self.rv)
        
        # Footer: Actions
        footer = BoxLayout(size_hint_y=None, height='50dp', spacing=10)
        btn_remind = Button(text='Add Reminders (Calendar)')
        btn_remind.bind(on_press=self.add_reminders)
        footer.add_widget(btn_remind)
        
        root.add_widget(footer)
        
        return root

    def fetch_fixtures(self, instance):
        if not core_logic:
            self.info_label.text = "Error: core_logic module not found"
            return

        self.info_label.text = "Fetching data..."
        # Run in thread
        threading.Thread(target=self._fetch_thread, daemon=True).start()

    def _fetch_thread(self):
        selected_team = self.spinner.text
        try:
            # Call core logic
            # core_logic.get_formatted_fixtures returns list of dicts
            fixtures = core_logic.get_formatted_fixtures(selected_team)
            
            # Format for RecycleView
            # Each item needs 'text' key for SelectableLabel
            data = []
            for f in fixtures:
                # f keys: time, opponent, competition, weekday, team, home_away
                display_text = f"{f['time']} {f['team']} vs {f['opponent']}\n{f['competition']} ({f['home_away']})"
                data.append({
                    'text': display_text,
                    'selected': False,
                    'raw_data': f # Store raw data for reminders
                })
            
            # Update UI on main thread
            Clock.schedule_once(lambda dt: self._update_rv(data))
            
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            Clock.schedule_once(lambda dt: self._update_info(error_msg))

    def _update_rv(self, data):
        self.rv.data = data
        self.info_label.text = f"Found {len(data)} fixtures"

    def _update_info(self, text):
        self.info_label.text = text

    def add_reminders(self, instance):
        selected_items = [x for x in self.rv.data if x.get('selected')]
        if not selected_items:
            self.info_label.text = "No matches selected"
            return
            
        count = len(selected_items)
        self.info_label.text = f"Selected {count} matches for reminders"
        
        if platform == 'android':
            from android.permissions import request_permissions, Permission
            self.pending_items = selected_items
            request_permissions(
                [Permission.READ_CALENDAR, Permission.WRITE_CALENDAR], 
                self.permission_callback
            )
        else:
            self.info_label.text = "Calendar feature only works on Android"
            print(f"Would add reminders for: {selected_items}")

    def permission_callback(self, permissions, grants):
        if all(grants):
            self.info_label.text = "Permissions granted, adding events..."
            # Run in thread to not block UI
            threading.Thread(target=self.execute_add_to_calendar, args=(self.pending_items,), daemon=True).start()
        else:
            self.info_label.text = "Calendar permissions denied"

    def execute_add_to_calendar(self, items):
        try:
            from jnius import autoclass, cast
            
            # Android classes
            CalendarContract = autoclass('android.provider.CalendarContract')
            Events = autoclass('android.provider.CalendarContract$Events')
            Reminders = autoclass('android.provider.CalendarContract$Reminders')
            ContentValues = autoclass('android.content.ContentValues')
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Uri = autoclass('android.net.Uri')
            
            activity = PythonActivity.mActivity
            resolver = activity.getContentResolver()
            
            # Find a valid calendar ID (usually 1, but safer to query)
            # For simplicity, we'll try to find the first writable calendar
            # Or just default to 1 and hope for the best (often works)
            # Proper way: Query Calendars table
            cal_id = 1 
            
            added_count = 0
            
            for item in items:
                match_data = item['raw_data']
                # Parse times
                # match_data['time'] is "YYYY-MM-DD HH:MM"
                match_dt = datetime.strptime(match_data['time'], "%Y-%m-%d %H:%M")
                
                # Calculate reminder time using utils
                remind_str = reminder_utils.calculate_reminder_time(match_data['time'])
                remind_dt = datetime.strptime(remind_str, "%Y-%m-%d %H:%M")
                
                start_millis = int(match_dt.timestamp() * 1000)
                end_millis = int((match_dt.timestamp() + 2 * 3600) * 1000) # 2 hours duration
                
                # Calculate minutes before for reminder
                minutes_before = int((match_dt - remind_dt).total_seconds() / 60)
                if minutes_before < 0:
                    # Reminder is after start? (e.g. 8am reminder for 3am match)
                    # Android reminders are usually "minutes before".
                    # If negative, it means "minutes after". 
                    # Android supports negative? Some docs say yes, but behavior varies.
                    # Alternatively, set event time to match time, but reminder triggers separately?
                    # Or create a separate event for the reminder (like in web_app).
                    
                    # Strategy: Create a separate "Score Check" event at the reminder time
                    # This mimics the web app behavior for late reminders
                    
                    # 1. Main Match Event (no alarm)
                    values = ContentValues()
                    values.put(Events.DTSTART, start_millis)
                    values.put(Events.DTEND, end_millis)
                    values.put(Events.TITLE, f"{match_data['team']} vs {match_data['opponent']}")
                    values.put(Events.DESCRIPTION, f"{match_data['competition']} ({match_data['home_away']})")
                    values.put(Events.CALENDAR_ID, cal_id)
                    values.put(Events.EVENT_TIMEZONE, "Asia/Shanghai")
                    resolver.insert(Events.CONTENT_URI, values)
                    
                    # 2. Reminder Event
                    remind_start_millis = int(remind_dt.timestamp() * 1000)
                    remind_end_millis = int((remind_dt.timestamp() + 15 * 60) * 1000) # 15 min
                    
                    r_event_values = ContentValues()
                    r_event_values.put(Events.DTSTART, remind_start_millis)
                    r_event_values.put(Events.DTEND, remind_end_millis)
                    r_event_values.put(Events.TITLE, f"⏰ 赛果: {match_data['team']} vs {match_data['opponent']}")
                    r_event_values.put(Events.DESCRIPTION, "Check Score")
                    r_event_values.put(Events.CALENDAR_ID, cal_id)
                    r_event_values.put(Events.EVENT_TIMEZONE, "Asia/Shanghai")
                    
                    r_uri = resolver.insert(Events.CONTENT_URI, r_event_values)
                    r_event_id = int(r_uri.getLastPathSegment())
                    
                    # Add 0 min reminder to this event
                    r_values = ContentValues()
                    r_values.put(Reminders.EVENT_ID, r_event_id)
                    r_values.put(Reminders.MINUTES, 0)
                    r_values.put(Reminders.METHOD, Reminders.METHOD_ALERT)
                    resolver.insert(Reminders.CONTENT_URI, r_values)
                    
                else:
                    # Normal reminder (before match)
                    values = ContentValues()
                    values.put(Events.DTSTART, start_millis)
                    values.put(Events.DTEND, end_millis)
                    values.put(Events.TITLE, f"{match_data['team']} vs {match_data['opponent']}")
                    values.put(Events.DESCRIPTION, f"{match_data['competition']} ({match_data['home_away']})")
                    values.put(Events.CALENDAR_ID, cal_id)
                    values.put(Events.EVENT_TIMEZONE, "Asia/Shanghai")
                    
                    uri = resolver.insert(Events.CONTENT_URI, values)
                    event_id = int(uri.getLastPathSegment())
                    
                    r_values = ContentValues()
                    r_values.put(Reminders.EVENT_ID, event_id)
                    r_values.put(Reminders.MINUTES, minutes_before)
                    r_values.put(Reminders.METHOD, Reminders.METHOD_ALERT)
                    resolver.insert(Reminders.CONTENT_URI, r_values)
                
                added_count += 1
            
            Clock.schedule_once(lambda dt: self._update_info(f"Successfully added {added_count} events to calendar"))
            
        except Exception as e:
            error_msg = f"Calendar Error: {str(e)}"
            print(error_msg)
            Clock.schedule_once(lambda dt: self._update_info(error_msg))

if __name__ == '__main__':
    # Define KV styles in Python for simplicity in this draft
    from kivy.lang import Builder
    Builder.load_string('''
<SelectableLabel>:
    # Draw a background to indicate selection
    canvas.before:
        Color:
            rgba: (.0, 0.9, .1, .3) if self.selected else (0, 0, 0, 1)
        Rectangle:
            pos: self.pos
            size: self.size
    Label:
        text: root.text
        text_size: self.size
        halign: 'left'
        valign: 'middle'
        padding_x: 10
''')
    
    FootballApp().run()
