"""
Claim Generator Service for Car Haulers (Dynamic & 1-Tap Copy)
Generates legally assertive, industry-standard English claim letters:
- Detention Claim ($75.00/hour after 2 free hours)
- TONU Claim ($250.00 Truck Ordered Not Used)
- In-Op Loading Fee Claim ($150.00 undisclosed winch fee)
Formatted in code blocks for 1-tap copy & paste into email or SMS to brokers.
"""

CLAIMS_INLINE_KEYBOARD = {
    "inline_keyboard": [
        [
            {"text": "⏱️ Детеншен ($75/ч)", "callback_data": "claim_detention"},
            {"text": "🛑 TONU ($250)", "callback_data": "claim_tonu"}
        ],
        [
            {"text": "🛠️ Неходовое авто (In-Op $150)", "callback_data": "claim_inop"}
        ]
    ]
}

def generate_detention_template(load_id="[LOAD#]", broker_name="[BROKER]", facility="[AUCTION/FACILITY]", hours="3", amount="225"):
    return f"""<b>⏱️ ОФИЦИАЛЬНАЯ ПРЕТЕНЗИЯ НА ДЕТЕНШЕН ($75/ЧАС):</b>
<i>Нажми на текст ниже, чтобы скопировать в 1 клик и отправить брокеру на email/SMS:</i>

<code>SUBJECT: URGENT: Detention Claim - Load #{load_id} - [CARRIER NAME]

Broker Accounting / Dispatch ({broker_name}),

Regarding Load #{load_id} (Rate Confirmation dated [DATE]):
Our driver arrived on schedule at the facility: {facility}.
• Check-in / Arrival Time: [ARRIVED TIME, e.g. 10:00 AM]
• Loading / Release Time: [DEPARTED TIME, e.g. 03:00 PM]
• Total Facility Time: 5.0 hours
• Standard Free Time: 2.0 hours
• Billable Detention Time: {hours}.0 hours

As per industry-standard car hauling terms and federal carrier regulations, detention for specialized auto transport equipment is billed at $75.00 per hour.

TOTAL DETENTION DUE: ${amount}.00 ({hours} hrs x $75.00/hr).

Signed gate pass / BOL with in and out timestamps is attached. 
Please issue a revised Rate Confirmation reflecting the additional ${amount}.00 detention immediately to ensure prompt load release and clean delivery.

Thank you,
[DISPATCHER / DRIVER NAME]
[CARRIER NAME] | USDOT / MC: [MC NUMBER]
Phone: [PHONE NUMBER]</code>

💡 <b>Совет диспетчера:</b>
1. Обязательно сфотографируй Gate Pass или подпись охранника/дилера со временем въезда и выезда.
2. Отправляй брокеру письмо <b>до того</b>, как уедешь с площадки, пока у тебя есть рычаг влияния!"""

def generate_tonu_template(load_id="[LOAD#]", broker_name="[BROKER]", facility="[PICKUP LOCATION]"):
    return f"""<b>🛑 ПРЕТЕНЗИЯ НА СРЫВ ПОГРУЗКИ / TONU ($250):</b>
<i>Нажми на текст ниже, чтобы скопировать в 1 клик и отправить брокеру:</i>

<code>SUBJECT: TONU Billing Notice - Load #{load_id} - [CARRIER NAME]

Broker Dispatch / Accounting ({broker_name}),

Please be advised that Load #{load_id} was canceled by the broker/shipper after carrier dispatch and arrival at the scheduled pickup location: {facility}.

• Driver & Unit: [DRIVER NAME] | Car Hauler Unit #[TRUCK#]
• Scheduled Pickup: [SCHEDULED TIME]
• On-Site Arrival Timestamp: [ARRIVAL TIME]
• Cancellation Notice: [CANCELLATION TIME]

Because equipment was reserved, deadhead miles were incurred, and other commercial loads were declined to service this dispatch, a standard Car Hauler TONU (Truck Ordered Not Used) fee of $250.00 is assessed pursuant to our carrier agreement.

Please issue an amended Rate Confirmation in the amount of $250.00 for TONU compensation to [DISPATCH EMAIL] within 24 hours.

Attached: GPS arrival log and original Rate Confirmation.

Sincerely,
[DISPATCHER NAME]
[CARRIER NAME] | MC #[MC NUMBER]</code>

💡 <b>Совет диспетчера:</b>
Если брокер пытается дать $150 вместо $250, напомни: для специализированного автовоза (Class 8 Stinger / 3-4 car wedge) подача под погрузку стоит дороже стандартного сухогруза."""

def generate_inop_template(load_id="[LOAD#]", broker_name="[BROKER]", vin="[VIN/VEHICLE]"):
    return f"""<b>🛠️ ПРЕТЕНЗИЯ ЗА НЕХОДОВОЕ АВТО (IN-OP WINCH FEE $150):</b>
<i>Нажми на текст ниже, чтобы скопировать в 1 клик:</i>

<code>SUBJECT: IN-OP / Winch Fee Required - Load #{load_id} - VIN: {vin}

Broker Team ({broker_name}),

At pickup ({vin}), vehicle was represented as RUN & DRIVE on the original Rate Confirmation.
Upon driver inspection, the vehicle is INOPERABLE (Dead battery, flat tires, mechanical failure / no keys).

Loading an inoperable vehicle onto a car hauler requires winching, manual rigging, and significant safety hazard exposure.

A standard In-Op Winch Fee of $150.00 is required to load this vehicle.

Driver is currently holding on site. Please send an updated Rate Confirmation with the $150.00 In-Op addition immediately so loading may proceed safely.

Attached: Photos of inoperable condition.

Best regards,
[CARRIER DISPATCH]</code>

💡 <b>Совет диспетчера:</b>
Не трогай авто лебедкой, пока брокер не пришлет обновленный Rate Con с добавленными $150! Если затащишь сам без согласования — брокер откажется платить постфактум."""

def handle_claim_command(user_text: str = "") -> tuple[str, dict]:
    """
    Main router for /claim, /detention, /tonu commands.
    Returns (text: str, reply_markup: dict or None).
    """
    cmd = user_text.strip().lower()
    if "tonu" in cmd or "срыв" in cmd or "отмен" in cmd:
        return generate_tonu_template(), None
    elif "inop" in cmd or "ин-оп" in cmd or "лебед" in cmd or "winch" in cmd:
        return generate_inop_template(), None
    elif "detention" in cmd or "простой" in cmd or "детеншен" in cmd:
        return generate_detention_template(), None

    menu_text = (
        "📋 <b>ГЕНЕРАТОР ОФИЦИАЛЬНЫХ ПРЕТЕНЗИЙ К БРОКЕРУ:</b>\n"
        "Выбери тип компенсации — получишь готовый боевой текст на английском для отправки брокеру в 1 клик:\n\n"
        "• ⏱️ <b>Детеншен (Detention):</b> <b>$75.00/час</b> после 2 часов бесплатного ожидания на погрузке/выгрузке (Copart, Manheim, Dealer).\n"
        "• 🛑 <b>Срыв погрузки (TONU):</b> <b>$250.00</b> при отмене груза брокером после прибытия автовоза.\n"
        "• 🛠️ <b>Неходовое авто (In-Op):</b> <b>+$150.00</b> за лебедку, если авто заявлено как Run & Drive, но не заводится.\n\n"
        "<i>Нажми на нужную кнопку ниже:</i>"
    )
    return menu_text, CLAIMS_INLINE_KEYBOARD
