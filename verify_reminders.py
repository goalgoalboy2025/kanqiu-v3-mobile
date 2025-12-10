from reminder_utils import calculate_reminder_time
import datetime

def test():
    # Test Case 1: Weekend early morning (should be 8:00)
    # 2023-12-10 is Sunday (Holiday/Weekend)
    # Wait, today is 2025-12-10 in the prompt env, which is Wednesday.
    # Let's pick a known weekend.
    # 2025-12-13 is Saturday.
    dt_weekend = "2025-12-13 03:00"
    res_weekend = calculate_reminder_time(dt_weekend)
    print(f"Weekend 03:00 (Expect 8:00): {res_weekend}")

    # Test Case 2: Workday early morning (should be 7:00)
    # 2025-12-10 is Wednesday (likely workday)
    dt_workday = "2025-12-10 03:00"
    res_workday = calculate_reminder_time(dt_workday)
    print(f"Workday 03:00 (Expect 7:00): {res_workday}")

    # Test Case 3: Normal time (should be -30 mins)
    dt_normal = "2025-12-10 20:00"
    res_normal = calculate_reminder_time(dt_normal)
    print(f"Normal 20:00 (Expect 19:30): {res_normal}")

if __name__ == "__main__":
    test()
