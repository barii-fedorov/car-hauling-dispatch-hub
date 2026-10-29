import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.aaa_fuel_feed import get_state_diesel_benchmark, sync_state_fuel_prices
from services.fuel_advisor import generate_fuel_recommendations

print("--- 1. Testing AAA State Benchmark for Oregon ---")
sync_state_fuel_prices()
bench_or = get_state_diesel_benchmark("OR")
print("Oregon Benchmark:", bench_or)

bench_fl = get_state_diesel_benchmark("FL")
print("Florida Benchmark:", bench_fl)

bench_ca = get_state_diesel_benchmark("CA")
print("California Benchmark:", bench_ca)

print("\n--- 2. Testing Fuel Recommendations for Eugene, Oregon ---")
res_eugene = generate_fuel_recommendations("Юджин, Орегон", driver_setup="Стингер 9-кар (Class 8)", cargo="Груженый 7-8 авто")
with open("test_eugene_result.txt", "w", encoding="utf-8") as f:
    f.write(res_eugene)
print("SUCCESS: Output written to test_eugene_result.txt")
