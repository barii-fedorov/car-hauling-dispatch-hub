"""
Active Diesel Fuel Intelligence & Rig Matching Service for Car Hauling
Tailors fuel stop recommendations strictly to the driver's equipment setup:
- Stinger 9-car & High-Mount: Commercial high-flow truck lanes only (Loves, Pilot/Flying J, TA/Petro).
- Pickup + 3-4 car Wedge: External RV/commercial lanes at discount chains (Buc-ee's, Circle K, Murphy USA).
Enforces: If rig is unknown, NEVER GUESS. Ask immediately!
"""
import sys
import json
from datetime import datetime

# Current representative regional diesel averages & IFTA tax rates
REGIONAL_DIESEL = {
    "PADD1_EAST_COAST": {
        "region": "East Coast (I-95 corridor)",
        "avg_retail_diesel": 3.65,
        "commercial_truckstop_avg": 3.72,
        "discount_station_avg": 3.42,
        "recommended_stops": {
            "stinger_highmount": ["Loves (Exit 104, VA)", "Pilot Flying J (Exit 106, NC)", "TA Petro (Florence, SC)"],
            "pickup_wedge": ["Buc-ee's (Florence, SC)", "Circle K (Richmond, VA)", "Wawa (Florida Turnpike plazas)"]
        },
        "ifta_high_tax_states": ["PA (78.5¢/gal)", "NY (38.1¢/gal)"],
        "ifta_low_tax_states": ["GA (35.0¢/gal)", "SC (28.75¢/gal)", "VA (30.8¢/gal)"]
    },
    "PADD2_MIDWEST": {
        "region": "Midwest (I-80, I-70, I-65 corridors)",
        "avg_retail_diesel": 3.48,
        "commercial_truckstop_avg": 3.55,
        "discount_station_avg": 3.25,
        "recommended_stops": {
            "stinger_highmount": ["Loves (Gary, IN)", "Pilot Flying J (Huber Heights, OH)", "TA (Effingham, IL)"],
            "pickup_wedge": ["Kwik Trip (Wisconsin / Iowa)", "Casey's General Store (high-canopy RV diesel)", "Thorntons"]
        },
        "ifta_high_tax_states": ["IL (54.5¢/gal)", "IN (57.0¢/gal)"],
        "ifta_low_tax_states": ["MO (27.0¢/gal) - TOP FUEL HAVEN", "OH (47.0¢/gal)"]
    },
    "PADD3_GULF_COAST": {
        "region": "Gulf Coast / Texas (I-10, I-35, I-20 corridors)",
        "avg_retail_diesel": 3.19,
        "commercial_truckstop_avg": 3.26,
        "discount_station_avg": 2.94,
        "recommended_stops": {
            "stinger_highmount": ["Loves (Sweetwater, TX)", "Pilot (Baytown, TX)", "Petro (San Antonio, TX)"],
            "pickup_wedge": ["Buc-ee's (New Braunfels / Bastrop, TX) - 50¢ cheaper!", "Murphy USA", "RaceTrac (Dallas/Fort Worth)"]
        },
        "ifta_high_tax_states": [],
        "ifta_low_tax_states": ["TX (20.0¢/gal) - CHEAPEST IN US", "LA (20.0¢/gal)"]
    },
    "PADD4_ROCKY_MOUNTAIN": {
        "region": "Rocky Mountain (I-25, I-80 WY corridor)",
        "avg_retail_diesel": 3.59,
        "commercial_truckstop_avg": 3.68,
        "discount_station_avg": 3.38,
        "recommended_stops": {
            "stinger_highmount": ["Little America (Cheyenne, WY)", "Loves (Ogden, UT)", "Pilot (Denver, CO)"],
            "pickup_wedge": ["Maverik (Adventure's First Stop - high canopy)", "Sinclair RV lanes"]
        },
        "ifta_high_tax_states": ["CO (20.5¢/gal)"],
        "ifta_low_tax_states": ["WY (24.0¢/gal)"]
    },
    "PADD5_WEST_COAST": {
        "region": "West Coast (California, I-5 corridor)",
        "avg_retail_diesel": 4.85,
        "commercial_truckstop_avg": 4.95,
        "discount_station_avg": 4.55,
        "recommended_stops": {
            "stinger_highmount": ["Pilot Flying J (Lebec, CA)", "Loves (Lost Hills, CA)", "Petro (Corning, CA)"],
            "pickup_wedge": ["Rotten Robbie (NorCal)", "Sinclair discount diesel (Sacramento)"]
        },
        "ifta_high_tax_states": ["CA (94.8¢/gal - EXTREME TAX)"],
        "ifta_low_tax_states": ["NV (27.0¢/gal) - Fill before entering CA!", "AZ (26.0¢/gal) - Fill at border!"]
    }
}

SETUP_INQUIRY_PROMPT = "Братуха, на чем идешь? Стингер 9-кар, хай-маунт или пикап с виджиком?"

def get_fuel_guidance(driver_setup=None, region="PADD3_GULF_COAST"):
    if not driver_setup or driver_setup.strip().lower() in ["unknown", "не знаю", "не указано", "none", ""]:
        return {
            "status": "need_setup",
            "message": SETUP_INQUIRY_PROMPT,
            "instruction": "НЕ УГАДЫВАЙ сетап! Стингеру нужны коммерческие трак-стопы с широким радиусом разворота, а виджик может сэкономить 40-50 центов на легковых заправках."
        }
    
    setup_lower = driver_setup.lower()
    is_semi = ("стингер" in setup_lower or "stinger" in setup_lower or 
               "хай-маунт" in setup_lower or "high-mount" in setup_lower or 
               "7-car" in setup_lower or "9-car" in setup_lower or "semi" in setup_lower)
    
    padd = REGIONAL_DIESEL.get(region, REGIONAL_DIESEL["PADD3_GULF_COAST"])
    
    if is_semi:
        return {
            "status": "ok",
            "driver_setup": "Class 8 Stinger / High-Mount",
            "fuel_zone": padd["region"],
            "expected_price_per_gal": padd["commercial_truckstop_avg"],
            "allowed_pumps": "Коммерческие грузовые колонки (Truck Lanes) с высокоскоростной подачей и сателлитным пистолетом (на два бака сразу).",
            "forbidden_pumps": "Категорически запрещено соваться на городские легковые заправки: радиус поворота 75-80ft, высота до 14ft, риск снести козырек или застрять на бордюре.",
            "recommended_chains": ["Loves", "Pilot Flying J", "TA / Petro"],
            "stops_sample": padd["recommended_stops"]["stinger_highmount"],
            "ifta_tip": f"Заливайся в дешевых штатах IFTA: {', '.join(padd['ifta_low_tax_states'])}. Избегай заправок под завязку в {', '.join(padd['ifta_high_tax_states'])}."
        }
    else:
        # Pickup + Wedge
        savings = round(padd["commercial_truckstop_avg"] - padd["discount_station_avg"], 2)
        return {
            "status": "ok",
            "driver_setup": "Pickup (RAM 3500 / Ford F-350) + Wedge 3-4 car",
            "fuel_zone": padd["region"],
            "expected_price_per_gal": padd["discount_station_avg"],
            "potential_savings": f"До ${savings}/галлон по сравнению с большими трак-стопами!",
            "allowed_pumps": "Внешние RV/легковые дизельные колонки (Buc-ee's, Circle K, Murphy USA, Wawa, Maverik).",
            "warning": "Внимание на занос хвоста (tail swing прицеп-виджика до 4 футов) и высоту верхнего яруса (обычно 10-12ft). Всегда выбирай крайние внешние колонки с прямым выездом.",
            "recommended_chains": ["Buc-ee's", "Circle K", "Murphy USA", "Maverik", "Wawa"],
            "stops_sample": padd["recommended_stops"]["pickup_wedge"],
            "ifta_tip": f"По IFTA: заправляйся в {', '.join(padd['ifta_low_tax_states'])}, чтобы минимизировать итоговый налог."
        }

if __name__ == "__main__":
    setup_arg = sys.argv[1] if len(sys.argv) > 1 else None
    res = get_fuel_guidance(setup_arg)
    print(json.dumps(res, indent=2, ensure_ascii=False))
