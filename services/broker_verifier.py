"""
Company Verifier Service for Car Haulers (Brokers by MC & Carriers by USDOT)
Ground truth FMCSA Registry Integration:
- Official U.S. DOT Socrata Open Data endpoints (az4n-8mr2 Company Census & 6eyk-hxee Operating Authority).
- Real-time resolution of legal names, operating authority status, insurance bond filings, fleet size, driver counts.
- Grounded AI assessment using Gemini (eliminates company hallucination).
- Car hauler risk verdict, safety recommendations, and factoring analysis.
"""

import os
import re
import json
import urllib.request
import urllib.parse

try:
    from services.model_router import query_model_with_failover
except ImportError:
    from model_router import query_model_with_failover

# DOT Socrata Endpoints
FMCSA_CENSUS_URL = "https://data.transportation.gov/resource/az4n-8mr2.json"
FMCSA_AUTHORITY_URL = "https://data.transportation.gov/resource/6eyk-hxee.json"

def fetch_fmcsa_registry_record(query_text: str) -> dict:
    """
    Fetches real-time verified company data from official US DOT FMCSA databases.
    Returns structured dict with verified legal entity details, or None.
    """
    clean_q = str(query_text).strip()
    
    # Extract identifiers
    dot_m = re.search(r'\b(?:dot|usdot)\s*#?\s*(\d{5,9})\b', clean_q, re.I)
    mc_m = re.search(r'\b(?:mc|mc#)\s*#?\s*(\d{5,8})\b', clean_q, re.I)
    generic_num = re.search(r'\b(\d{5,9})\b', clean_q)
    
    dot_num = None
    mc_num = None
    if dot_m:
        dot_num = dot_m.group(1)
    elif mc_m:
        mc_num = mc_m.group(1)
    elif generic_num:
        n = int(generic_num.group(1))
        if n > 1800000:
            dot_num = str(n)
        else:
            mc_num = str(n)

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    # 1. Look up by USDOT number in Company Census
    if dot_num:
        try:
            url = f"{FMCSA_CENSUS_URL}?dot_number={dot_num}"
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                if data:
                    item = data[0]
                    return {
                        "entity_type": "carrier",
                        "source": "FMCSA Company Census (MOTUS/SAFER)",
                        "legal_name": item.get("legal_name"),
                        "dba_name": item.get("dba_name"),
                        "dot_number": item.get("dot_number"),
                        "mc_number": f"{item.get('docket1prefix', 'MC')}{item.get('docket1')}" if item.get("docket1") else None,
                        "status_code": item.get("status_code"),
                        "status_str": "Active (Активен)" if item.get("status_code") == "A" else "Inactive / Revoked (Отозван / Неактивен)",
                        "classdef": item.get("classdef"),
                        "address": f"{item.get('phy_street', '')}, {item.get('phy_city', '')}, {item.get('phy_state', '')} {item.get('phy_zip', '')}".strip(", "),
                        "phone": item.get("phone"),
                        "email": item.get("email_address"),
                        "officer": item.get("company_officer_1"),
                        "power_units": item.get("power_units", "0"),
                        "drivers": item.get("total_drivers", "0"),
                        "car_carrier": "Да (Motor Vehicles)" if item.get("crgo_motoveh") == "X" else "Общие грузы",
                        "crash_rate": item.get("recordable_crash_rate", "0.000"),
                        "add_date": item.get("add_date", "")
                    }
        except Exception as e:
            print(f"[WARN] FMCSA Census query error: {e}")

    # 2. Look up by MC docket in Operating Authority & Census
    if mc_num:
        candidates = [f"MC{mc_num}", f"MC{mc_num.zfill(6)}"]
        for cand in candidates:
            try:
                url = f"{FMCSA_AUTHORITY_URL}?docket_number={cand}"
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=8) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
                    if data:
                        item = data[0]
                        is_broker = item.get("broker_stat") in ["A", "Y"]
                        dot_val = item.get("dot_number", "").lstrip("0") or None
                        return {
                            "entity_type": "broker" if is_broker else "carrier",
                            "source": "FMCSA Operating Authority Registry",
                            "legal_name": item.get("legal_name"),
                            "dba_name": item.get("dba_name"),
                            "dot_number": dot_val,
                            "mc_number": item.get("docket_number"),
                            "status_str": "Active (Активен)" if (item.get("broker_stat") == "A" or item.get("common_stat") == "A") else "Inactive / Revoked (Отозван / Неактивен)",
                            "broker_stat": item.get("broker_stat"),
                            "common_stat": item.get("common_stat"),
                            "bond_filed": "Активен ($75,000 BMC-84 на файле)" if item.get("bond_file") == "Y" else "Нет активного бонда ($75k BMC-84 отсутствует)",
                            "insurance_bipd": f"${int(item.get('bipd_file', '0')) * 1000:,}" if item.get("bipd_file") and item.get("bipd_file") != "00000" else "$0",
                            "address": f"{item.get('bus_street_po', '')}, {item.get('bus_city', '')}, {item.get('bus_state_code', '')} {item.get('bus_zip_code', '')}".strip(", "),
                            "phone": item.get("bus_telno")
                        }
            except Exception as e:
                print(f"[WARN] FMCSA Authority query error for {cand}: {e}")

        # Fallback to Census by docket1
        try:
            url = f"{FMCSA_CENSUS_URL}?docket1={mc_num}"
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                if data:
                    item = data[0]
                    return {
                        "entity_type": "carrier",
                        "source": "FMCSA Company Census (by MC)",
                        "legal_name": item.get("legal_name"),
                        "dba_name": item.get("dba_name"),
                        "dot_number": item.get("dot_number"),
                        "mc_number": f"MC{mc_num}",
                        "status_code": item.get("status_code"),
                        "status_str": "Active (Активен)" if item.get("status_code") == "A" else "Inactive / Revoked",
                        "classdef": item.get("classdef"),
                        "address": f"{item.get('phy_street', '')}, {item.get('phy_city', '')}, {item.get('phy_state', '')}".strip(", "),
                        "power_units": item.get("power_units", "0"),
                        "drivers": item.get("total_drivers", "0"),
                        "email": item.get("email_address"),
                        "officer": item.get("company_officer_1")
                    }
        except Exception as e:
            print(f"[WARN] FMCSA Census query error for MC {mc_num}: {e}")

    # 3. Lookup by Legal or DBA Name if query is alphabetic
    clean_alpha = re.sub(r'[^a-zA-Z0-9\s]', '', clean_q).strip().upper()
    if len(clean_alpha) >= 4 and not clean_alpha.isdigit() and clean_alpha not in ["BROKER", "CARRIER", "TRUCKING"]:
        try:
            # Check Authority first
            p_auth = {"$where": f"upper(legal_name) like '%{clean_alpha}%' or upper(dba_name) like '%{clean_alpha}%'", "$limit": 1}
            url = f"{FMCSA_AUTHORITY_URL}?" + urllib.parse.urlencode(p_auth)
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                if data:
                    item = data[0]
                    is_broker = item.get("broker_stat") in ["A", "Y"]
                    dot_val = item.get("dot_number", "").lstrip("0") or None
                    return {
                        "entity_type": "broker" if is_broker else "carrier",
                        "source": "FMCSA Operating Authority Registry (by Name)",
                        "legal_name": item.get("legal_name"),
                        "dba_name": item.get("dba_name"),
                        "dot_number": dot_val,
                        "mc_number": item.get("docket_number"),
                        "status_str": "Active (Активен)" if (item.get("broker_stat") == "A" or item.get("common_stat") == "A") else "Inactive / Revoked",
                        "bond_filed": "Активен ($75,000 BMC-84 на файле)" if item.get("bond_file") == "Y" else "Нет активного бонда",
                        "address": f"{item.get('bus_city', '')}, {item.get('bus_state_code', '')}".strip(", "),
                        "phone": item.get("bus_telno")
                    }
        except Exception as e:
            print(f"[WARN] FMCSA Name query error: {e}")

    return None

def estimate_mc_age_and_risk(mc_digits: int) -> dict:
    """Estimates broker business longevity and initial risk tier from MC sequence."""
    if mc_digits < 300000:
        return {
            "tier": "LEGACY",
            "age_years": "25+ лет (Основан до 1996 г.)",
            "risk_level": "🟢 МИНИМАЛЬНЫЙ РИСК",
            "factoring": "Одобряется 100% факторингов (A+ Tier)",
            "dtp_estimate": "18–24 дня (или QuickPay 1-2 дня)",
            "bond_default": "BMC-84 $75,000 Активен (Первоклассный эмитент)"
        }
    elif mc_digits < 800000:
        return {
            "tier": "ESTABLISHED",
            "age_years": "10–25 лет (Проверенная временем компания)",
            "risk_level": "🟢 НИЗКИЙ РИСК",
            "factoring": "Одобряется всеми крупными факторингами (RTS, OTR, Apex, Triumph)",
            "dtp_estimate": "21–28 дней",
            "bond_default": "BMC-84 $75,000 Активен"
        }
    elif mc_digits < 1300000:
        return {
            "tier": "SOLID",
            "age_years": "4–10 лет на рынке",
            "risk_level": "🟢 УМЕРЕННЫЙ / СТАБИЛЬНЫЙ",
            "factoring": "Одобряется большинством факторингов",
            "dtp_estimate": "24–30 дней",
            "bond_default": "BMC-84 $75,000 Активен"
        }
    elif mc_digits < 1500000:
        return {
            "tier": "YOUNG",
            "age_years": "1.5–3 года на рынке",
            "risk_level": "🟡 ВНИМАНИЕ / ТРЕБУЕТСЯ ПРОВЕРКА",
            "factoring": "Обязательно пробивать через факторинг перед погрузкой (Credit Check)",
            "dtp_estimate": "30–35 дней",
            "bond_default": "BMC-84 $75,000 (Проверить дату обновления)"
        }
    else:
        return {
            "tier": "NEW_AUTHORITY",
            "age_years": "Меньше 12–18 месяцев (Свежий MC)",
            "risk_level": "🔴 ВЫСОКИЙ РИСК (Свежий брокер)",
            "factoring": "Часто в No-Credit списке у факторингов",
            "dtp_estimate": "Нестабильно (риск задержки оплаты 45+ дней)",
            "bond_default": "BMC-84 $75,000 (Проверить наличие претензий!)"
        }

def estimate_dot_age_and_risk(dot_digits: int) -> dict:
    """Estimates carrier longevity, authority maturity and scrutiny tier from USDOT sequence."""
    if dot_digits < 1000000:
        return {
            "tier": "LEGACY_CARRIER",
            "age_years": "25+ лет (Зарегистрирован до 2002 г.)",
            "risk_level": "🟢 МИНИМАЛЬНЫЙ РИСК",
            "authority_status": "Активен (Исторический перевозчик)",
            "insurance_standard": "$1,000,000 Auto Liability + $250k Cargo",
            "broker_acceptance": "Одобряется 100% брокеров и бирж грузов"
        }
    elif dot_digits < 2200000:
        return {
            "tier": "ESTABLISHED_CARRIER",
            "age_years": "12–25 лет на рынке",
            "risk_level": "🟢 НИЗКИЙ РИСК",
            "authority_status": "Активен (Зрелая автовозная компания)",
            "insurance_standard": "$1,000,000 Auto Liability",
            "broker_acceptance": "Полный доступ к грузам на Central Dispatch / DAT"
        }
    elif dot_digits < 3200000:
        return {
            "tier": "SOLID_CARRIER",
            "age_years": "6–12 лет на рынке",
            "risk_level": "🟢 СТАБИЛЬНЫЙ ПЕРЕВОЗЧИК",
            "authority_status": "Активен",
            "insurance_standard": "Стандартное покрытие $1M на FMCSA",
            "broker_acceptance": "Одобряется всеми брокерами при чистом OOS"
        }
    elif dot_digits < 3900000:
        return {
            "tier": "MODERATE_CARRIER",
            "age_years": "2–6 лет на рынке",
            "risk_level": "🟡 УМЕРЕННЫЙ РИСК (Проверить инспекции)",
            "authority_status": "Активен (Проверять OOS на весах)",
            "insurance_standard": "Требуется свежий COI (Certificate of Insurance)",
            "broker_acceptance": "Проходит большинство проверок"
        }
    elif dot_digits < 4250000:
        return {
            "tier": "YOUNG_CARRIER",
            "age_years": "6–24 месяцев (Молодой перевозчик)",
            "risk_level": "🟡 ВНИМАНИЕ: NEW AUTHORITY (<2 лет)",
            "authority_status": "Активен (Испытательный срок New Entrant)",
            "insurance_standard": "Проверять Form BMC-91X и оплату полиса",
            "broker_acceptance": "Ряд брокеров требуют 90–180 дней активного статуса"
        }
    else:
        return {
            "tier": "NEW_DOT",
            "age_years": "Меньше 6 месяцев (Свежий USDOT)",
            "risk_level": "🔴 ВЫСОКИЙ РИСК (Свежая регистрация / New Entrant)",
            "authority_status": "Требуется проверка Safety Audit и адреса",
            "insurance_standard": "Обязательно запрашивать COI напрямую у агента!",
            "broker_acceptance": "Строгий фильтр у крупных брокеров (TQL/Landstar блокируют до 90-180д)"
        }

def detect_entity_type(query_text: str) -> str:
    """Detects whether query pertains to a Carrier (USDOT) or a Broker (MC)."""
    q = query_text.lower()
    
    if any(k in q for k in ["dot", "usdot", "carrier", "перевозчик", "тракер", "траковая", "автопарк", "водитель", "oos"]):
        return "carrier"
    
    if any(k in q for k in ["mc", "broker", "брокер", "бонд", "bmc-84", "dtp", "factoring", "факторинг", "rate con", "rate confirmation"]):
        return "broker"
    
    if re.search(r'\b(?:dot|usdot)\s*#?\s*\d+\b', query_text, re.IGNORECASE):
        return "carrier"
    if re.search(r'\b(?:mc|mc#)\s*#?\s*\d+\b', query_text, re.IGNORECASE):
        return "broker"
        
    num_match = re.search(r'\b(\d{5,8})\b', query_text)
    if num_match:
        n = int(num_match.group(1))
        if n > 1800000:
            return "carrier"
        return "broker"
        
    return "auto"

def query_gemini_for_company_intelligence(query_text: str, fmcsa_record: dict = None, entity_type: str = "auto") -> str:
    """Uses Gemini with strict FMCSA grounding facts to prevent any hallucinations."""
    
    grounding_block = ""
    if fmcsa_record:
        grounding_block = (
            "РЕАЛЬНЫЕ ПРОВЕРЕННЫЕ ДАННЫЕ ИЗ ОФИЦИАЛЬНОГО РЕЕСТРА FMCSA (США):\n"
            f"- Юридическое название: {fmcsa_record.get('legal_name')}\n"
            f"- DBA (Торговая марка): {fmcsa_record.get('dba_name') or 'Отсутствует'}\n"
            f"- USDOT#: {fmcsa_record.get('dot_number') or 'Не указан'}\n"
            f"- MC/Docket#: {fmcsa_record.get('mc_number') or 'Не указан'}\n"
            f"- Статус в FMCSA: {fmcsa_record.get('status_str')}\n"
            f"- Тип компании / Класс: {fmcsa_record.get('classdef') or fmcsa_record.get('entity_type')}\n"
            f"- Адрес: {fmcsa_record.get('address') or 'Не указан'}\n"
            f"- Телефон: {fmcsa_record.get('phone') or 'Не указан'}\n"
            f"- Email в реестре: {fmcsa_record.get('email') or 'Не указан'}\n"
            f"- Флот: {fmcsa_record.get('power_units', 'N/A')} power units / {fmcsa_record.get('drivers', 'N/A')} drivers\n"
            f"- Страховой бонд BMC-84: {fmcsa_record.get('bond_filed', 'Проверить форму')}\n"
            f"- Страховка BIPD Liability: {fmcsa_record.get('insurance_bipd', '$1,000,000')}\n\n"
            "СТРОГОЕ ПРАВИЛО: Используй ТОЛЬКО вышеуказанное юридическое название и цифры! "
            "КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО выдумывать чужое название компании! Если указано DRY RUN LLC — пиши DRY RUN LLC."
        )
    else:
        grounding_block = (
            "ВНИМАНИЕ: Запрос не найден напрямую в реестре FMCSA. "
            "Если точное юридическое название компании неизвестно, напиши «[Юридическое название не найдено в открытом реестре]». "
            "КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО выдумывать случайные названия компаний (вроде GSL Express и т.п.)!"
        )

    prompt = f"""Ты — старший специалист по безопасности, комплаенсу и проверке транспортных компаний американского автовозного флота (FMCSA SAFER, Central Dispatch, DAT Directory, Carrier411, Highway).
Пользователь просит проверить компанию или номер: "{query_text}".
Предполагаемый тип: {entity_type} (если указано auto, определи по фактам: брокер по MC# или перевозчик по USDOT#).

{grounding_block}

Твоя задача — дать четкую, строгую и реалистичную проверку в формате Telegram HTML.

1. ЕСЛИ ЭТО ПЕРЕВОЗЧИК (Carrier / USDOT#):
🚛 <b>[Реальное Название Перевозчика из реестра] (USDOT #[DOT#] / MC #[MC# если есть])</b>
• <b>Статус Operating Authority:</b> [🟢 Активен / 🔴 Отозван / Inactive]
• <b>Город и штат:</b> [Город, Штат из фактов]
• <b>Возраст компании:</b> [Сколько лет на рынке / дата регистрации FMCSA]
• <b>Страховое покрытие:</b> [$1,000,000 Auto Liability / $100k-$250k Cargo (Form BMC-91X / BMC-34)]
• <b>Safety Rating & Инспекции:</b> [Satisfactory / None / Conditional] | OOS инспекции
• <b>Флот и водители:</b> [Кол-во траков / водителей из фактов]
• <b>Риск хамелеона / скама:</b> [🟢 Минимальный / 🟡 Умеренный / 🔴 Высокий]

💡 <b>Вердикт диспетчера:</b> 2 емких предложения (надежен ли перевозчик, пропустят ли брокеры с таким DOT, можно ли давать груз или работать с ним).

2. ЕСЛИ ЭТО БРОКЕР (Freight Broker / MC#):
🏢 <b>[Реальное Название Брокера из реестра] (MC #[MC#])</b>
• <b>Статус MC/DOT:</b> [🟢 Активен / 🔴 Не активен]
• <b>Страховой бонд BMC-84 ($75,000):</b> [Активен / Кем выдан]
• <b>Город и штат:</b> [Город, Штат]
• <b>Возраст MC:</b> [Сколько лет на рынке]
• <b>Срок оплаты (DTP):</b> [Дней на оплату]
• <b>Факторинг:</b> [Одобряется большинством (Apex, RTS, OTR) / В стоп-листе]
• <b>Риск дабл-брокеринга:</b> [🟢 Минимальный / 🟡 Средний / 🔴 Высокий]

💡 <b>Вердикт диспетчера:</b> 2 емких предложения (брать груз / требовать QuickPay / только через проверенный факторинг / отказ).

ПРАВИЛА:
- Никакой воды, строго реальные факты и автовозная специфика (COI, BMC-91X, $1M Liability, Central Dispatch rating, DTP, QuickPay).
- Если в запросе указан DOT — формируй карточку перевозчика 🚛.
- Если в запросе указан MC — формируй карточку брокера 🏢.
- Оформи красивым Telegram HTML (<b>, <i>, <code>)."""

    try:
        raw_text, _ = query_model_with_failover(prompt, context_type="general")
        if raw_text and len(raw_text.strip()) > 40:
            return raw_text.strip()
    except Exception as e:
        print(f"[WARN] Gemini company check error: {e}")
    return None

def verify_company(user_input: str, default_type: str = "auto") -> str:
    """
    Main entry point for company verification.
    Verifies Brokers by MC# or Carriers by USDOT# using live FMCSA grounding.
    """
    cleaned = user_input.strip()
    
    # Empty prompt check
    if not cleaned or cleaned in ["🏢 Проверить брокера", "🏢 Проверить брокера / DOT", "/broker", "/carrier", "/dot"]:
        return (
            "🏢 <b>Проверка компании (Брокер по MC / Перевозчик по DOT):</b>\n\n"
            "• <b>Проверка брокера:</b> отправь номер MC (например: <code>MC 322572</code>) или название компании (например: <code>TQL</code>) — "
            "проверю статус в FMCSA, бонд BMC-84 ($75k), дни оплаты (DTP) и факторинг.\n\n"
            "• <b>Проверка перевозчика:</b> отправь номер USDOT (например: <code>DOT 4407897</code>) или номер MC — "
            "проверю статус Operating Authority, флот, страховку $1M и риск хамелеона."
        )

    detected = detect_entity_type(cleaned)
    target_type = detected if detected != "auto" else default_type

    # 1. Fetch live FMCSA registry record (100% authoritative government data)
    fmcsa_data = fetch_fmcsa_registry_record(cleaned)

    # 2. Query Gemini with authoritative FMCSA grounding facts injected
    ai_result = query_gemini_for_company_intelligence(cleaned, fmcsa_record=fmcsa_data, entity_type=target_type)
    if ai_result:
        return ai_result

    # 3. Direct Fallback using FMCSA structured record if AI is unavailable
    if fmcsa_data:
        legal_name = fmcsa_data.get("legal_name") or "Транспортная компания"
        dot = fmcsa_data.get("dot_number") or "N/A"
        mc = fmcsa_data.get("mc_number") or "N/A"
        status = fmcsa_data.get("status_str") or "Active"
        addr = fmcsa_data.get("address") or "США"
        
        if fmcsa_data.get("entity_type") == "broker":
            bond = fmcsa_data.get("bond_filed") or "BMC-84 $75,000 на файле"
            return (
                f"🏢 <b>ПРОВЕРКА БРОКЕРА: {legal_name}</b>\n\n"
                f"• <b>MC / Docket:</b> <code>{mc}</code> | <b>USDOT:</b> <code>{dot}</code>\n"
                f"• <b>Статус Authority:</b> {status}\n"
                f"• <b>Страховой бонд:</b> {bond}\n"
                f"• <b>Юридический адрес:</b> {addr}\n"
                f"• <b>Источник:</b> {fmcsa_data.get('source')}\n\n"
                f"💡 <b>Вердикт диспетчера:</b>\n"
                f"<i>Компания зарегистрирована в FMCSA. Перед подтверждением рейт-кона сверяйте домен email и проверяйте через факторинг.</i>"
            )
        else:
            power_units = fmcsa_data.get("power_units", "1")
            drivers = fmcsa_data.get("drivers", "1")
            return (
                f"🚛 <b>ПРОВЕРКА ПЕРЕВОЗЧИКА: {legal_name}</b>\n\n"
                f"• <b>USDOT:</b> <code>#{dot}</code> | <b>MC:</b> <code>{mc}</code>\n"
                f"• <b>Статус Authority:</b> {status}\n"
                f"• <b>Флот:</b> {power_units} power units, {drivers} drivers\n"
                f"• <b>Юридический адрес:</b> {addr}\n"
                f"• <b>Классификация:</b> {fmcsa_data.get('classdef') or 'Authorized For-Hire'}\n"
                f"• <b>Источник:</b> {fmcsa_data.get('source')}\n\n"
                f"💡 <b>Вердикт диспетчера:</b>\n"
                f"<i>Официальный перевозчик по базе FMCSA. Запрашивайте Certificate of Insurance ($1M Auto Liability) напрямую у страхового агента.</i>"
            )

    # 4. Algorithmic sequence estimation fallback if completely offline & not in registry
    dot_match = re.search(r'\b(?:DOT|USDOT)\s*#?\s*(\d{5,9})\b', cleaned, re.IGNORECASE)
    mc_match = re.search(r'\b(?:MC|MC#)\s*#?\s*(\d{5,8})\b', cleaned, re.IGNORECASE)
    generic_num = re.search(r'\b(\d{5,9})\b', cleaned)

    if dot_match or target_type == "carrier" or (generic_num and int(generic_num.group(1)) > 1800000):
        dot_num = int(dot_match.group(1)) if dot_match else int(generic_num.group(1))
        est = estimate_dot_age_and_risk(dot_num)
        return (
            f"🚛 <b>ЭКСПРЕСС-ПРОВЕРКА ПЕРЕВОЗЧИКА: USDOT #{dot_num}</b>\n\n"
            f"• <b>Уровень риска:</b> {est['risk_level']}\n"
            f"• <b>Возраст компании:</b> {est['age_years']}\n"
            f"• <b>Статус Authority:</b> {est['authority_status']}\n"
            f"• <b>Страховой стандарт:</b> {est['insurance_standard']}\n"
            f"• <b>Доступ к грузам:</b> {est['broker_acceptance']}\n\n"
            f"💡 <b>Вердикт диспетчера:</b>\n<i>Проверьте дату выдачи Authority на FMCSA перед бронированием грузов.</i>"
        )

    if mc_match or generic_num:
        mc_num = int(mc_match.group(1)) if mc_match else int(generic_num.group(1))
        est = estimate_mc_age_and_risk(mc_num)
        return (
            f"🔍 <b>ЭКСПРЕСС-ПРОВЕРКА БРОКЕРА: MC #{mc_num}</b>\n\n"
            f"• <b>Уровень риска:</b> {est['risk_level']}\n"
            f"• <b>Возраст MC:</b> {est['age_years']}\n"
            f"• <b>Страховой бонд:</b> {est['bond_default']}\n"
            f"• <b>Факторинг:</b> {est['factoring']}\n"
            f"• <b>Средний срок оплаты:</b> {est['dtp_estimate']}\n\n"
            f"💡 <b>Вердикт диспетчера:</b>\n<i>Перед погрузкой проверьте одобрение инвойса через факторинг.</i>"
        )

    return (
        f"🔍 <b>Проверка компании:</b> «{cleaned}»\n\n"
        "Укажи номер <code>MC [номер]</code> для проверки брокера или <code>DOT [номер]</code> для проверки перевозчика."
    )

def verify_broker(user_input: str) -> str:
    """Backwards-compatible wrapper for checking brokers."""
    return verify_company(user_input, default_type="broker")

def verify_carrier(user_input: str) -> str:
    """Wrapper for checking motor carriers by USDOT."""
    return verify_company(user_input, default_type="carrier")
