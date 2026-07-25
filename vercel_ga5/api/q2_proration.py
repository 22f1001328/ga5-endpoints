"""
Q2 - Spec-Driven Development: The Proration Bug
POST body: {old_price, new_price, days_remaining, days_in_actual_month, spec: "v1"|"v2"}
Return: {"charge": number}
  v1: charge = (new_price - old_price) * (days_remaining / 30)
  v2: charge = (new_price - old_price) * (days_remaining / days_in_actual_month)
Tolerance $0.01. Must respond fast.
"""

def compute_charge(body: dict) -> float:
    old_price = float(body["old_price"])
    new_price = float(body["new_price"])
    days_remaining = float(body["days_remaining"])
    spec = body.get("spec", "v1")

    if spec == "v1":
        divisor = 30.0
    elif spec == "v2":
        divisor = float(body["days_in_actual_month"])
    else:
        raise ValueError(f"unknown spec: {spec}")

    return (new_price - old_price) * (days_remaining / divisor)


# quick self-test with the scenario in the prompt:
# Feb 2028 (leap year, 29 days), upgrade day 14, old=19, new=49
# days_remaining = day 14 through end inclusive = 29 - 14 + 1 = 16
if __name__ == "__main__":
    v1 = compute_charge({"old_price": 19, "new_price": 49,
                         "days_remaining": 16, "days_in_actual_month": 29, "spec": "v1"})
    v2 = compute_charge({"old_price": 19, "new_price": 49,
                         "days_remaining": 16, "days_in_actual_month": 29, "spec": "v2"})
    print(f"v1 charge = {v1:.4f}  (expected (49-19)*16/30 = {30*16/30:.4f})")
    print(f"v2 charge = {v2:.4f}  (expected (49-19)*16/29 = {30*16/29:.4f})")
