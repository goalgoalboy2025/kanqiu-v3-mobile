from datetime import datetime, timedelta
try:
    import chinesecalendar
    HAS_CHINESE_CALENDAR = True
except ImportError:
    HAS_CHINESE_CALENDAR = False

def is_holiday_safe(date_obj):
    """
    判断是否为节假日（安全模式，如果库不可用则回退到周末判断）
    """
    if HAS_CHINESE_CALENDAR:
        try:
            return chinesecalendar.is_holiday(date_obj)
        except Exception:
            pass
    # Fallback: simple weekend check (Saturday=5, Sunday=6)
    return date_obj.weekday() >= 5

def calculate_reminder_time(match_datetime_str):
    """
    根据比赛时间和节假日规则计算提醒时间。
    
    规则：
    1. 中国大陆法定节假日 0:00 至 7:00 举行的比赛，在当日 8:00 进行提醒。
    2. 非法定节假日 0:00 至 7:00 举行的比赛，在当日 7:00 进行提醒。
    3. 其他时间的比赛，在比赛开始前半小时进行提醒。
    
    Args:
        match_datetime_str (str): 格式如 "2023-10-27 19:30"
        
    Returns:
        str: 提醒时间，格式 "2023-10-27 19:00"
    """
    try:
        # 假设输入格式为 "%Y-%m-%d %H:%M"
        match_time = datetime.strptime(match_datetime_str, "%Y-%m-%d %H:%M")
    except ValueError:
        # 尝试其他可能的格式，或者返回错误
        return "时间格式错误"

    match_date = match_time.date()
    match_hour = match_time.hour
    match_minute = match_time.minute
    
    # 判断是否在 0:00 至 7:00 之间 (包含 0:00，包含 7:00)
    # 用户表述 "0:00至7:00"。
    # 如果是 7:00 整的比赛，是否包含？通常包含。
    is_early_morning = (match_hour < 7) or (match_hour == 7 and match_minute == 0)
    
    if is_early_morning:
        # 判断是否为法定节假日 (包括周末，除非调休)
        # is_holiday 返回 True 如果是休息日（周末或节假日）
        # is_workday 返回 True 如果是工作日（周一至周五或调休工作日）
        if is_holiday_safe(match_date):
            # 法定节假日 -> 8:00 提醒
            reminder_time = match_time.replace(hour=8, minute=0, second=0)
        else:
            # 非法定节假日 -> 7:00 提醒
            reminder_time = match_time.replace(hour=7, minute=0, second=0)
    else:
        # 其他时间 -> 提前 30 分钟
        reminder_time = match_time - timedelta(minutes=30)
        
    return reminder_time.strftime("%Y-%m-%d %H:%M")

if __name__ == "__main__":
    # 测试用例
    test_cases = [
        ("2023-10-01 03:00", "节假日凌晨"), # 10.1 是国庆
        ("2023-10-02 07:00", "节假日7点"),
        ("2023-10-04 03:00", "工作日凌晨"), # 假设这天不是节假日，需查表
        ("2023-10-27 19:30", "普通晚上"),
        ("2023-10-28 00:30", "周六凌晨"), # 周六是休息日
    ]
    
    print("测试结果:")
    for dt_str, desc in test_cases:
        print(f"{desc} ({dt_str}) -> 提醒: {calculate_reminder_time(dt_str)}")
