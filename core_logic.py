import requests
import os
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz
import re
import json
import concurrent.futures

TEAMS = {
    "Arsenal": "arsenal",
    "Man City": "manchester-city",
    "Liverpool": "liverpool",
    "Chelsea": "chelsea",
    "Real Madrid": "real-madrid",
    "Barcelona": "barcelona",
    "Atletico Madrid": "atletico-madrid",
    "Bayern Munich": "bayern-munich",
    "PSG": "paris-saint-germain",
    "China": "china",
    "Germany": "germany",
    "France": "france",
    "Spain": "spain",
    "Brazil": "brazil",
    "Argentina": "argentina",
    "Portugal": "portugal",
    "England": "england"
}

def normalize_team_name(name):
    """
    Normalize team name to the key in TEAMS dict if possible.
    e.g. "Manchester City" -> "Man City"
    """
    if not name:
        return name
        
    # Check if it's already a key
    if name in TEAMS:
        return name
        
    name_lower = name.lower().strip()
    
    # Check exact match with keys (case insensitive)
    for key in TEAMS:
        if key.lower() == name_lower:
            return key
            
    # Check against values (slugs)
    for key, slug in TEAMS.items():
        # slug is like "manchester-city"
        # name might be "Manchester City"
        slug_space = slug.replace("-", " ")
        if name_lower == slug_space or name_lower == slug:
            return key
            
    # Common variations map
    variations = {
        "manchester united": "Man Utd",
        "man utd": "Man Utd",
        "tottenham": "Tottenham Hotspur",
        "spurs": "Tottenham Hotspur",
        "wolves": "Wolverhampton Wanderers",
        "brighton": "Brighton and Hove Albion",
        "paris saint germain": "PSG",
        "paris sg": "PSG",
        "paris": "PSG"
    }
    
    if name_lower in variations:
        return variations[name_lower]
        
    # Check for partial containment for known complex names
    # e.g. "Brighton" in "Brighton and Hove Albion"
    # But be careful of "Man" in "Man City" and "Man Utd"
    
    return name

def fetch_fixtures(team_slug, date_str=None):
    url = f"https://www.skysports.com/{team_slug}-scores-fixtures"
    if date_str:
        url += f"/{date_str}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.text
        else:
            print(f"Failed to fetch data for {team_slug} (date={date_str}): Status {response.status_code}")
    except Exception as e:
        print(f"Error fetching data for {team_slug}: {e}")
    
    return None

def parse_fixtures(html, team_name):
    if not html:
        return []
        
    soup = BeautifulSoup(html, 'html.parser')
    fixtures = []
    
    # Strategy: Parse data-state attribute
    elements = soup.find_all(attrs={"data-state": True})
    
    for el in elements:
        try:
            data_state = el['data-state']
            data = json.loads(data_state)
            
            # Check if it's a match object (has 'start' and 'teams')
            if isinstance(data, dict) and 'start' in data and 'teams' in data:
                start = data.get('start', {})
                date_str = start.get('date') # e.g. "Sunday 30th November"
                time_str = start.get('time') # e.g. "16:30" or "TBC"
                
                if not date_str or not time_str:
                    continue
                
                # Parse date
                # Format usually: "Sunday 30th November"
                parts = date_str.split(' ')
                if len(parts) < 3:
                    continue
                
                day_str = parts[1] # 30th
                month_str = parts[2] # November
                
                day = re.sub(r'(st|nd|rd|th)', '', day_str) # 30
                
                # Assuming year is current year or next year
                # We need to be smart about year rollover (e.g. December to January)
                now = datetime.now()
                current_year = now.year
                
                # Try current year first
                dt_str = f"{current_year} {day} {month_str} {time_str}"
                try:
                    dt = datetime.strptime(dt_str, "%Y %d %B %H:%M")
                except ValueError:
                    # TBC time or invalid format
                    continue
                
                # Adjust year logic
                # If the parsed date is more than 6 months in the past, it's likely next year
                if (now - dt).days > 180:
                    dt = dt.replace(year=current_year + 1)
                # If the parsed date is more than 6 months in the future, it's likely last year (unlikely for upcoming)
                elif (dt - now).days > 180:
                    dt = dt.replace(year=current_year - 1)
                
                # Convert to UTC
                # Sky Sports times are usually UK time (GMT/BST)
                # For simplicity, we assume UK time.
                # UK is UTC+0 in winter, UTC+1 in summer.
                # We can use pytz to localize to London
                uk_tz = pytz.timezone('Europe/London')
                dt_uk = uk_tz.localize(dt)
                dt_utc = dt_uk.astimezone(pytz.UTC)
                
                # Determine opponent
                home_team = data['teams']['home']['name']['full']
                away_team = data['teams']['away']['name']['full']
                
                # Heuristic to find opponent
                # Use slug for better matching (e.g. "Man City" -> "manchester-city" -> "manchester city")
                slug = TEAMS.get(team_name, "")
                slug_norm = slug.replace("-", " ")
                
                home_team_norm = home_team.lower().replace("-", " ")
                away_team_norm = away_team.lower().replace("-", " ")
                team_name_lower = team_name.lower()
                
                match_home = (team_name_lower in home_team_norm) or \
                             (slug and slug in home_team_norm) or \
                             (slug_norm and slug_norm in home_team_norm)
                             
                match_away = (team_name_lower in away_team_norm) or \
                             (slug and slug in away_team_norm) or \
                             (slug_norm and slug_norm in away_team_norm)
                
                if match_home:
                    opponent = away_team
                    is_home = True
                elif match_away:
                    opponent = home_team
                    is_home = False
                else:
                    # Fallback if team name not found (e.g. "Man City" vs "Manchester City")
                    # We assume the page belongs to the team, so check which one is NOT the team
                    # But here we might process unrelated matches if the page has them?
                    # Sky pages usually only show relevant matches.
                    # Let's just take the one that isn't similar to team_name
                    # Simplified: assume home if not sure
                    opponent = f"{home_team} vs {away_team}"
                    is_home = True # irrelevant
                
                comp_name = data.get('competition', {}).get('name', {}).get('full', 'Unknown')
                
                fixtures.append({
                    'datetime_utc': dt_utc,
                    'opponent': opponent,
                    'competition': comp_name,
                    'team': team_name, # Record which team this is for
                    'is_home': is_home
                })
                
        except Exception:
            continue
            
    return fixtures

def get_team_fixtures(team_name):
    slug = TEAMS.get(team_name)
    if not slug:
        return []
    
    fixtures = []
    
    # Fetch current month
    html1 = fetch_fixtures(slug)
    fixtures.extend(parse_fixtures(html1, team_name))
    
    # Fetch next month
    now = datetime.now()
    if now.month == 12:
        next_month = now.replace(year=now.year+1, month=1, day=1)
    else:
        next_month = now.replace(month=now.month+1, day=1)
    
    date_str = next_month.strftime("%Y-%m-%d")
    html2 = fetch_fixtures(slug, date_str)
    fixtures.extend(parse_fixtures(html2, team_name))
    
    return fixtures

def get_formatted_fixtures(team_name="Arsenal"):
    """
    Fetches and formats fixtures.
    team_name can be a single string or "All".
    """
    
    all_fixtures = []
    
    if team_name == "All":
        # Fetch all teams concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_team = {executor.submit(get_team_fixtures, name): name for name in TEAMS.keys()}
            for future in concurrent.futures.as_completed(future_to_team):
                try:
                    data = future.result()
                    all_fixtures.extend(data)
                except Exception as e:
                    print(f"Error fetching {future_to_team[future]}: {e}")
    else:
        all_fixtures = get_team_fixtures(team_name)
    
    if not all_fixtures:
        return []
        
    now = datetime.now(pytz.UTC)
    end_date = now + timedelta(days=7)
    
    # Filter upcoming
    upcoming = [f for f in all_fixtures if now <= f['datetime_utc'] <= end_date]
    
    # Deduplicate matches
    # Key can be (time, sorted_teams)
    seen = set()
    unique_upcoming = []
    for f in upcoming:
        # We need to reconstruct the full match string to check duplicates
        # But we only have opponent and team.
        # Let's make a unique key
        # opponent vs team
        
        # Normalize names for deduplication key
        team_norm = normalize_team_name(f['team'])
        opponent_norm = normalize_team_name(f['opponent'])
        
        teams_set = sorted([team_norm, opponent_norm])
        key = (f['datetime_utc'], tuple(teams_set))
        if key not in seen:
            seen.add(key)
            unique_upcoming.append(f)
    upcoming = unique_upcoming
        
    upcoming.sort(key=lambda x: x['datetime_utc'])
    
    beijing_tz = pytz.timezone('Asia/Shanghai')
    
    comp_map = {
        "Premier League": "英超",
        "UEFA Champions League": "欧冠",
        "FA Cup": "足总杯",
        "Carabao Cup": "联赛杯",
        "Community Shield": "社区盾",
        "Friendly Match": "友谊赛",
        "La Liga": "西甲",
        "Spanish La Liga": "西甲",
        "Bundesliga": "德甲",
        "German Bundesliga": "德甲",
        "Ligue 1": "法甲",
        "French Ligue 1": "法甲",
        "German DFB Cup": "德国杯"
    }

    # Expanded Team Translation Map
    team_map = {
        "Arsenal": "阿森纳",
        "Man City": "曼城",
        "Manchester City": "曼城",
        "Liverpool": "利物浦",
        "Chelsea": "切尔西",
        "Real Madrid": "皇家马德里",
        "Barcelona": "巴塞罗那",
        "Atletico Madrid": "马德里竞技",
        "Bayern Munich": "拜仁慕尼黑",
        "PSG": "巴黎圣日耳曼",
        "Paris Saint-Germain": "巴黎圣日耳曼",
        "Tottenham Hotspur": "热刺",
        "Man Utd": "曼联",
        "Manchester United": "曼联",
        "Aston Villa": "阿斯顿维拉",
        "Newcastle United": "纽卡斯尔",
        "West Ham United": "西汉姆联",
        "Brighton and Hove Albion": "布莱顿",
        "Brentford": "布伦特福德",
        "Fulham": "富勒姆",
        "Crystal Palace": "水晶宫",
        "Nottingham Forest": "诺丁汉森林",
        "Wolverhampton Wanderers": "狼队",
        "Everton": "埃弗顿",
        "Luton Town": "卢顿",
        "Burnley": "伯恩利",
        "Sheffield United": "谢菲尔德联",
        "Bournemouth": "伯恩茅斯",
        "Girona": "赫罗纳",
        "Athletic Club": "毕尔巴鄂竞技",
        "Real Betis": "皇家贝蒂斯",
        "Real Sociedad": "皇家社会",
        "Sevilla": "塞维利亚",
        "Valencia": "瓦伦西亚",
        "Villarreal": "比利亚雷亚尔",
        "Bayer Leverkusen": "勒沃库森",
        "Stuttgart": "斯图加特",
        "RB Leipzig": "莱比锡红牛",
        "Borussia Dortmund": "多特蒙德",
        "Eintracht Frankfurt": "法兰克福",
        "Inter Milan": "国际米兰",
        "AC Milan": "AC米兰",
        "Juventus": "尤文图斯",
        "Napoli": "那不勒斯",
        "Roma": "罗马",
        "Lazio": "拉齐奥",
        "Atalanta": "亚特兰大",
        "Monaco": "摩纳哥",
        "Brest": "布雷斯特",
        "Lille": "里尔",
        "Nice": "尼斯",
        "Lens": "朗斯",
        "Marseille": "马赛",
        "Lyon": "里昂",
        "Rennes": "雷恩",
        "Sunderland": "桑德兰",
        "Leeds United": "利兹联",
        "Southampton": "南安普顿",
        "Leicester City": "莱斯特城",
        "Ipswich Town": "伊普斯维奇",
        "1. FC Union Berlin": "柏林联合",
        
        # National Teams
        "China": "中国",
        "Germany": "德国",
        "France": "法国",
        "Spain": "西班牙",
        "Brazil": "巴西",
        "Argentina": "阿根廷",
        "Portugal": "葡萄牙",
        "England": "英格兰"
    }
    
    results = []
    for f in upcoming:
        dt_bj = f['datetime_utc'].astimezone(beijing_tz)
        time_str = dt_bj.strftime("%Y-%m-%d %H:%M")
        comp_name = f['competition']
        comp_cn = comp_map.get(comp_name, comp_name)
        
        # Translate teams
        team_en = f['team']
        team_cn = team_map.get(team_en, team_en)
        
        opponent_en = f['opponent']
        # Try exact match first
        opponent_cn = team_map.get(opponent_en, opponent_en)
        
        # If not exact match, try partial match logic only if it's still English
        # Actually, Sky Sports names are pretty standard.
        # If we don't have a translation, we show English.
        
        home_away = "主场" if f.get('is_home', True) else "客场"
        
        results.append({
            "time": time_str,
            "opponent": opponent_cn,
            "competition": comp_cn,
            "weekday": dt_bj.strftime("%A"),
            "team": team_cn,
            "home_away": home_away
        })
        
    return results


def get_next_week_fixtures():
    # Test "All" fetching
    print("Testing 'All' teams fetch...")
    results = get_formatted_fixtures("All")
    
    now_str = datetime.now().strftime('%Y-%m-%d')
    print(f"\n未来一周赛事 (起始日期: {now_str}):")
    
    if not results:
        print("无即将开始的比赛")
    
    for res in results:
        print(f"[{res['time']}] {res['team']} vs {res['opponent']} ({res['competition']})")

if __name__ == "__main__":
    get_next_week_fixtures()
