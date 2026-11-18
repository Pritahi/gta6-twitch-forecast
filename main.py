import json
import os
import math
import glob
from datetime import datetime, timedelta, timezone

def parse_iso(s):
    if s.endswith('Z'):
        s = s[:-1] + '+00:00'
    return datetime.fromisoformat(s)

def get_weighted_quantile(data, weights, quantile):
    """
    data: list of values
    weights: list of weights corresponding to data
    quantile: target quantile (0 to 1)
    """
    if not data:
        return 0.0
    
    # Sort by data values
    combined = sorted(zip(data, weights), key=lambda x: x[0])
    sorted_data, sorted_weights = zip(*combined)
    
    total_weight = sum(sorted_weights)
    if total_weight == 0:
        return sorted_data[len(sorted_data) // 2]
    
    target_weight = quantile * total_weight
    cumulative_weight = 0.0
    
    for val, weight in zip(sorted_data, sorted_weights):
        cumulative_weight += weight
        if cumulative_weight >= target_weight:
            return val
    return sorted_data[-1]

def solve():
    input_dir = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
    output_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    
    os.makedirs(output_dir, exist_ok=True)
    
    input_files = glob.glob(os.path.join(input_dir, "*.in"))
    
    for file_path in input_files:
        with open(file_path, 'r') as f:
            try:
                case = json.load(f)
            except Exception:
                continue
        
        # known[0].viewers = hour-1 print p
        known = case.get("known", [])
        if not known:
            continue
        p = float(known[0].get("viewers", 0))
        if p <= 0:
            p = 1.0 # Fallback
            
        comparables = case.get("comparables", [])
        valid_comparables = []
        
        for comp in comparables:
            day_start_str = comp.get("day_start")
            hourly = comp.get("hourly", [])
            if not day_start_str or not hourly:
                continue
            
            day_start = parse_iso(day_start_str)
            h_minus_1 = day_start - timedelta(hours=1)
            
            # Find hour-1 (pc)
            pc = None
            for h_data in hourly:
                h_from_str = h_data.get("from")
                if h_from_str and parse_iso(h_from_str) == h_minus_1:
                    pc = float(h_data.get("viewers", 0))
                    break
            
            if pc is not None and pc > 0:
                # Extract launch-day curve: viewers of hours 1..24 starting at its day_start
                # We need hours 2..24 for the forecast
                curve = {}
                for h_data in hourly:
                    h_from_str = h_data.get("from")
                    if not h_from_str:
                        continue
                    h_from = parse_iso(h_from_str)
                    
                    # h_from should be day_start + (hour_idx - 1) hours
                    # So hour_idx = (h_from - day_start) / 1 hour + 1
                    diff = h_from - day_start
                    hour_idx = int(diff.total_seconds() / 3600) + 1
                    
                    if 1 <= hour_idx <= 24:
                        curve[hour_idx] = float(h_data.get("viewers", 0))
                
                # Weight: exp(-abs(ln(p/pc))/0.5)
                weight = math.exp(-abs(math.log(p / pc)) / 0.5)
                valid_comparables.append({
                    "pc": pc,
                    "weight": weight,
                    "curve": curve
                })
        
        forecast_hours = []
        # Target hours 2..24
        for h in range(2, 25):
            pool_ln_ratio = []
            weights = []
            for comp in valid_comparables:
                val_h = comp["curve"].get(h)
                if val_h is not None and val_h > 0:
                    pool_ln_ratio.append(math.log(val_h / comp["pc"]))
                    weights.append(comp["weight"])
            
            if not pool_ln_ratio:
                # Fallback if no data for this hour
                q_values = [p] * 5
            else:
                levels = [0.05, 0.25, 0.5, 0.75, 0.95]
                qs = [get_weighted_quantile(pool_ln_ratio, weights, q) for q in levels]
                
                # (4) Calibrate: multiply log-spread by 1.25, keeping median fixed
                median_idx = 2
                median_val = qs[median_idx]
                calibrated_qs = []
                for q_val in qs:
                    diff = q_val - median_val
                    calibrated_qs.append(median_val + diff * 1.25)
                
                # q_tau = p * exp(quantile)
                q_values = [max(0.01, p * math.exp(cq)) for cq in calibrated_qs]
                # Ensure ascending
                q_values.sort()
                
            forecast_hours.append({
                "hour": h,
                "q": q_values
            })
            
        output_data = {"hours": forecast_hours}
        file_id = os.path.basename(file_path).replace(".in", "")
        output_file_path = os.path.join(output_dir, f"{file_id}.out")
        
        with open(output_file_path, 'w') as f:
            json.dump(output_data, f, separators=(',', ':'))

if __name__ == "__main__":
    solve()
