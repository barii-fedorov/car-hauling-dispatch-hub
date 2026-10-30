"""
Company Verifier Service for Car Haulers (Brokers by MC & Carriers by USDOT)
Dynamic AI & FMCSA Knowledge Base for Freight Brokers and Motor Carriers:
- Broker verification: MC#, BMC-84 Surety Bond ($75,000), DTP, Factoring approvals, double-broker risk.
- Carrier verification: USDOT#, Operating Authority status, Insurance ($1M Liability / Cargo),
  FMCSA Safety Rating, OOS (Out-of-Service) rates vs National Averages, fleet size, chameleon/fraud risk.
- Actionable advice for car haulers, owner-operators, and dispatchers.
"""

import os
import re
import json

try:
    from services.model_router import query_model_with_failover
except ImportError:
    from model_router import query_model_with_failover

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
    
    # Explicit carrier keywords
    if any(k in q for k in ["dot", "usdot", "carrier", "перевозчик", "тракер", "траковая", "автопарк", "водитель", "oos"]):
        return "carrier"
    
    # Explicit broker keywords
    if any(k in q for k in ["mc", "broker", "брокер", "бонд", "bmc-84", "dtp", "factoring", "факторинг", "rate con", "rate confirmation"]):
        return "broker"
    
    # Pattern matching
    if re.search(r'\b(?:dot|usdot)\s*#?\s*\d+\b', query_text, re.IGNORECASE):
        return "carrier"
    if re.search(r'\b(?:mc|mc#)\s*#?\s*\d+\b', query_text, re.IGNORECASE):
        return "broker"
        
    num_match = re.search(r'\b(\d{5,8})\b', query_text)
    if num_match:
        n = int(num_match.group(1))
        # USDOT numbers issued recently are typically > 1,800,000, while MC numbers max out around 1,750,000
        if n > 1800000:
            return "carrier"
        return "broker"
        
    return "auto"

def query_gemini_for_company_intelligence(query_text: str, entity_type: str = "auto") -> str:
    """Uses Gemini via Model Router for real-time freight broker or motor carrier reputation assessment."""
    prompt = f"""Ты — старший специалист по безопасности, комплаенсу и проверке транспортных компаний американского автовозного флота (FMCSA SAFER, Central Dispatch, DAT Directory, Carrier411, Highway).
Пользователь просит проверить компанию или номер: "{query_text}".
Предполагаемый тип: {entity_type} (если указано auto, сам определи: брокер это по MC# или перевозчик по USDOT#).

Твоя задача — дать четкую, строгую и реалистичную проверку в формате Telegram HTML.

1. ЕСЛИ ЭТО ПЕРЕВОЗЧИК (Carrier / USDOT#):
🚛 <b>[Название Перевозчика] (USDOT #[DOT#] / MC #[MC# если есть])</b>
• <b>Статус Operating Authority:</b> [🟢 Активен / 🔴 Отозван / Inactive] (Common / Contract / Property Carrier)
• <b>Возраст компании:</b> [Сколько лет на рынке / дата регистрации FMCSA]
• <b>Страховое покрытие:</b> [$1,000,000 Auto Liability / $100k-$250k Cargo (Form BMC-91X / BMC-34)]
• <b>Safety Rating & Инспекции:</b> [Satisfactory / None / Conditional] | Driver OOS: [X]% (нац. норма 6.7%), Vehicle OOS: [Y]% (нац. норма 22.2%)
• <b>Флот и водители:</b> [Кол-во траков / водителей, ДТП за 24 мес]
• <b>Риск хамелеона / скама:</b> [🟢 Минимальный / 🟡 Умеренный / 🔴 Высокий (виртуальный адрес, частая смена DOT, свежее юрлицо)]

💡 <b>Вердикт диспетчера:</b> 2 емких предложения (надежен ли перевозчик, пропустят ли брокеры с таким DOT, можно ли давать груз или работать с ним).

2. ЕСЛИ ЭТО БРОКЕР (Freight Broker / MC#):
🏢 <b>[Название Брокера] (MC #[MC#])</b>
• <b>Статус MC/DOT:</b> [🟢 Активен / 🔴 Не активен]
• <b>Страховой бонд BMC-84 ($75,000):</b> [Активен / Кем выдан]
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
    Verifies Brokers by MC# or Carriers by USDOT#.
    """
    cleaned = user_input.strip()
    
    # Empty prompt check
    if not cleaned or cleaned in ["🏢 Проверить брокера", "🏢 Проверить брокера / DOT", "/broker", "/carrier", "/dot"]:
        return (
            "🏢 <b>Проверка компании (Брокер по MC / Перевозчик по DOT):</b>\n\n"
            "• <b>Проверка брокера:</b> отправь номер MC (например: <code>MC 1045231</code>) или название (например: <code>TQL</code>) — "
            "проверю бонд BMC-84 ($75k), дни оплаты (DTP), факторинг и дабл-брокеринг.\n\n"
            "• <b>Проверка перевозчика:</b> отправь номер USDOT (например: <code>DOT 3892104</code>) или название компании — "
            "проверю статус Operating Authority, страховку $1M, OOS-инспекции (Out of Service) и риск хамелеона."
        )

    detected = detect_entity_type(cleaned)
    target_type = detected if detected != "auto" else default_type

    # 1. Try Gemini deep search via Model Router
    ai_result = query_gemini_for_company_intelligence(cleaned, entity_type=target_type)
    if ai_result:
        return ai_result

    # 2. Algorithmic fallback if AI is offline
    dot_match = re.search(r'\b(?:DOT|USDOT)\s*#?\s*(\d{5,9})\b', cleaned, re.IGNORECASE)
    mc_match = re.search(r'\b(?:MC|MC#)\s*#?\s*(\d{5,8})\b', cleaned, re.IGNORECASE)
    generic_num = re.search(r'\b(\d{5,9})\b', cleaned)

    # Carrier fallback
    if dot_match or target_type == "carrier" or (generic_num and int(generic_num.group(1)) > 1800000):
        dot_num = int(dot_match.group(1)) if dot_match else int(generic_num.group(1))
        est = estimate_dot_age_and_risk(dot_num)
        
        if est["tier"] in ["LEGACY_CARRIER", "ESTABLISHED_CARRIER", "SOLID_CARRIER"]:
            advice = "Проверенный перевозчик с солидной историей FMCSA. Брокеры выдают грузы без ограничений."
        elif est["tier"] == "MODERATE_CARRIER":
            advice = "Стабильный перевозчик. Рекомендуется сверить свежий Certificate of Insurance ($1M Auto Liability / $100k+ Cargo)."
        else:
            advice = "Внимание: молодой перевозчик (New Authority)! Уточняйте требования брокера по возрасту компании (многие требуют от 90-180 дней активного статуса)."

        return (
            f"🚛 <b>ЭКСПРЕСС-ПРОВЕРКА ПЕРЕВОЗЧИКА: USDOT #{dot_num}</b>\n\n"
            f"• <b>Уровень риска:</b> {est['risk_level']}\n"
            f"• <b>Возраст компании:</b> {est['age_years']}\n"
            f"• <b>Статус Authority:</b> {est['authority_status']}\n"
            f"• <b>Страховой стандарт:</b> {est['insurance_standard']}\n"
            f"• <b>Доступ к грузам:</b> {est['broker_acceptance']}\n\n"
            f"💡 <b>Вердикт диспетчера:</b>\n<i>{advice}</i>"
        )

    # Broker fallback
    if mc_match or generic_num:
        mc_num = int(mc_match.group(1)) if mc_match else int(generic_num.group(1))
        est = estimate_mc_age_and_risk(mc_num)

        if est["tier"] in ["LEGACY", "ESTABLISHED", "SOLID"]:
            advice = "Груз можно брать спокойно. Факторинг одобрит инвойс в день сдачи. Если нужен быстрый кэш — бери QuickPay за 2-3%."
        elif est["tier"] == "YOUNG":
            advice = "Перед погрузкой обязательно сделай Credit Check через свой факторинг. Сверяй email диспетчера — домен должен совпадать с официальным сайтом брокера!"
        else:
            advice = "Внимание: свежий MC! Высокий риск дабл-брокеринга или срыва оплаты. Требуй предоплату QuickPay 50% на солярку или бери только при 100% одобрении факторинга!"

        return (
            f"🔍 <b>ЭКСПРЕСС-ПРОВЕРКА БРОКЕРА: MC #{mc_num}</b>\n\n"
            f"• <b>Уровень риска:</b> {est['risk_level']}\n"
            f"• <b>Возраст MC:</b> {est['age_years']}\n"
            f"• <b>Страховой бонд:</b> {est['bond_default']}\n"
            f"• <b>Факторинг:</b> {est['factoring']}\n"
            f"• <b>Средний срок оплаты:</b> {est['dtp_estimate']}\n\n"
            f"💡 <b>Вердикт для оунера:</b>\n<i>{advice}</i>"
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
