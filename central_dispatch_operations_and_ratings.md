---
title: "Регламент работы на Central Dispatch: бронирование, репутационный комплаенс и арбитраж транзакционных рейтингов"
category: "Аукционы и биржевая логистика"
tags: ["central-dispatch", "cox-automotive", "load-board", "ratings", "arbitration", "reviews"]
source_notebook: "Грузовики на базу"
notebook_id: "e493af15-d51c-414f-aca9-484bb99fc356"
---

# Регламент работы на Central Dispatch: бронирование, репутационный комплаенс и арбитраж транзакционных рейтингов

Архитектура и правила работы с биржей Central Dispatch Платформа Central Dispatch, функционирующая в составе цифровой экосистемы Cox Automotive, представляет собой фундаментальную биржу распределения грузов в сегменте автомобильной логистики Соединенных Штатов Америки [1]. Платформа связывает лицензированных автоброкеров, дилерские сети, страховые аукционы и коммерческих перевозчиков в единое информационное пространство [3]. Достижение высокой операционной маржинальности и стабильная загрузка автопарка требуют от перевозчика не просто выполнения транспортной работы, но и строгого соблюдения платформенных регламентов, превентивной защиты юридического профиля и глубокого понимания механизмов верификации данных [4].

Профиль компании, валидация и комплаенс-настройки Профиль автотранспортной компании на Central Dispatch является визитной карточкой перевозчика, на основе которой брокерские алгоритмы и риск-менеджеры принимают решение о выдаче подтверждения ставки (Rate Confirmation) [4]. Первичная настройка аккаунта требует сопряжения федеральных регулирующих баз данных и внутренних параметров учетной записи платформы [4].

Регистрация и подтверждение полномочий начинаются с привязки федеральных номеров Motor Carrier (MC) и US Department of Transportation (USDOT) [4]. Система Central Dispatch в режиме реального времени сверяет введенные данные с федеральной базой FMCSA SAFER (Safety and Fitness Electronic Records) [4]. Любые расхождения в официальном юридическом наименовании юридического лица, физическом адресе регистрации, а также наличие нерешенных вопросов по безопасности в системе SMS (Safety Measurement System) или подозрения в создании компании-клона (Chameleon Carrier) приводят к блокировке аккаунта или автоматическому отклонению запросов брокерскими TMS [4].

Интеграция страхового сертификата (Certificate of Insurance — COI) представляет собой ключевой элемент комплаенса [4]. На платформу загружается действующий COI от андеррайтера с рейтингом A.M. Best не ниже «A-» [9]. В качестве держателя сертификата (Certificate Holder) обязательно указывается юридическое лицо платформы — Central Dispatch / Cox Automotive [9]. В автовозной индустрии критически важно дифференцировать стандартное страхование грузов (Motor Truck Cargo — MTC) и профильный полис Auto-Hauler Cargo (On-Hook Insurance) [9]. Стандартный полис MTC в большинстве случаев исключает возмещение ущерба, возникшего в процессах погрузки, выгрузки или крепления транспортного средства (Loading and Unloading Operations) [9]. При наступлении страхового события на рампе автовоза отсутствие специализированного покрытия On-Hook переводит всю финансовую ответственность на перевозчика, провоцируя судебные иски и перманентный бан на бирже [9]. При истечении срока действия страхового полиса Central Dispatch немедленно ограничивает функционал личного кабинета до момента подтверждения пролонгации страховым агентом [4].

Точное указание типов оборудования исключает логистические сбои, вызванные несоответствием габаритов или массы перевозимой партии [12]. В профиле фиксируются спецификации используемых тягачей и прицепов.

Тип оборудования (Equipment Type) Конфигурация тягача и прицепа Средняя вместимость Минимальный требуемый лимит Cargo Insurance Целевые категории перевозимых ТС 3-4 Car Wedge Тягач Class 3–5 (Dually Pickup) + прицеп типа Gooseneck Wedge [12] 3–4 единицы (сегмент седанов и компактных кроссоверов) [12] $100,000 – $250,000 [8] Локальные дилерские переброски, аукционные единичные выкупы, частный клиентский сектор [9] 7-9 Car Stinger-Steer Седельный тягач Class 8 со специализированным прицепом High-Mount или Stinger Low-Mount [12] 7–10 единиц (смешанные партии легковых авто и SUV) [12] $250,000 – $500,000 [9] Межрегиональный магистральный транзит (OTR Long-Haul), оптовые лоты Manheim/Adesa, заводские партии [9] Enclosed Trailer Магистральный тягач + закрытый изотермический/тентованный прицеп с гидравлическим лифтом (Liftgate) [9] 2–6 единиц [12] $500,000 – $1,000,000+ [9] Классические раритетные автомобили, суперкары, прототипы, премиальные электромобили (EV) [9] Lowboy / Step Deck Тягач тяжелого класса + низкорамная платформа с аппарелями [15] 1–3 единицы (в зависимости от тоннажа) [15] $250,000 – $500,000 [9] Высокие коммерческие фургоны (Sprinter Vans), бронированные ТС, легкая спецтехника [15] Операционная скорость диспетчерской службы оптимизируется посредством инструментов автоматизации поиска — сохраненных фильтров (Saved Searches) и мгновенных оповещений (Dispatch Alerts) [16]. Высоколиквидные грузы с высокими тарифами забираются с площадки в течение 30–60 секунд с момента их размещения [16]. Диспетчер формирует специализированные выборки по ключевым транспортным коридорам, задавая радиусы забора (Origin Radius) и доставки (Destination Radius) в диапазоне от 50 до 150 миль от основных магистралей [16]. Настройка каналов уведомлений через SMS и корпоративную почту позволяет моментально реагировать на появление грузов [16]. Использование расширенных уровней подписки предоставляет возможность подключать до 1000 оповещений в сутки на профиль и распределять лиды между несколькими логистами одновременно [19].

Этика и правила коммуникации с брокерами на платформе Деловое взаимодействие на платформе регулируется этическими и юридическими нормами, призванными предотвратить дезорганизацию логистических цепочек [11]. Первичный контакт с брокером посредством платформенного функционала запросов (Dispatch Requests / Inquiries) или телефонной связи требует профессиональной подготовки данных [4]. Диспетчер обязан заранее рассчитать совместимость габаритов, оценить общую массу партии, проверить высоту груза (не превышая нормативные 13 футов 6 дюймов / 14 футов в зависимости от штата) и подтвердить физическую готовность трака к забору в указанные временные окна [3].

Торги по ставкам должны вестись аргументированно [4]. Запрос надбавки за милю должен подкрепляться объективными факторами: удаленностью локации от основных магистралей (Deadhead Miles), сложным рельефом, неисправным состоянием ТС (Inoperable Vehicle) или сжатыми сроками [5]. Непрофессиональные действия, такие как массовая рассылка завышенных ценовых предложений без намерения брать груз или непрекращающиеся звонки по лотам с пометкой Firm Rate, приводят к блокировке учетной записи перевозчика во внутренних базах данных экспедиторов [4].

Процедура фиксации бронирования исключает любые устные договоренности [5]. Назначение заказа в интерфейсе Central Dispatch и перевод его в статус Assigned или Not Signed накладывает на стороны предварительные обязательства, однако единственным имеющим юридическую силу документом остается подтверждение ставки (Broker-Carrier Agreement / Rate Con) [4].

Перед снятием груза с биржи и отправкой трака на точку диспетчер обязан провести комплексный аудит Rate Con по следующим пунктам:

Идентификация ТС:

Полное соответствие марки, модели, года выпуска и последних цифр VIN-кода данным, указанным на бирже [18].

Работоспособность (Operational Status):

Четкое разграничение статусов Runs & Drives и Inoperable [11]. В случае транспортировки аварийного или неподвижного ТС документ должен прямо предусматривать плату за использование лебедки (Winch Fee: стандартно от $100 до $250) и подтверждать доступность погрузчика (Forklift) на обеих сторонах маршрута [5].

Временные окна (Pickup & Delivery Windows):

Исключение скрытых положений о жестких минутных окнах (Strict Appointments), нарушение которых влечет несоразмерные штрафы [3].

Условия расчетов (Payment Terms):

Фиксация точных сроков выплаты (QuickPay 1–2 дня с дисконтом, стандартный расчет ACH 15–30 дней, оплата по факту выгрузки COP/COD), формы расчета (Direct Deposit, Comchek, Zelle) и сторон, несущих расходы за перевод средств [6].

Аукционная документация:

Наличие корректных разрешений на вывоз (Gate Pass, Release PIN, Buyer Number, Lot Number), а также четких правил ожидания (Detention Policy) [11].

Категорически запрещается отзывать заявку водителя с других маршрутов, удалять предложения с доски или подтверждать приемку груза внутри цифровой системы Central Dispatch до момента получения и проверки подписанного обеими сторонами Rate Con на официальную корпоративную почту логистической компании [4].

Механика системы рейтингов (Transactional Ratings) В рамках масштабной модернизации платформы Central Dispatch отказался от устаревшей недифференцированной шкалы оценок в пользу системы верифицированных транзакционных рейтингов (Transactional Ratings) [1]. Главным новшеством модели стала жесткая привязка оценки к подтвержденной платформенной сделке [1]. Оставить отзыв о работе контрагента теперь технически возможно только по грузам, прошедшим официальный цикл диспетчеризации и переведенным в финальный статус Delivered или Cancelled [1].

Три критерия оценки перевозчика (3 Core Rating Criteria) Система Transactional Ratings оценивает каждую транзакцию комплексно: пользователь выставляет общий балл (Overall Rating) от 1 до 5 звезд и детализирует работу партнера по трем специализированным функциональным категориям [3].

+------------------------------------+                |       TRANSACTIONAL RATINGS        |                |          Overall (1-5★)            |                +-----------------+------------------+                                  |         +------------------------+------------------------+         |                        |                        |         v                        v                        v+------------------+    +------------------+    +------------------+|    Timeliness    |    |  Communication   |    |  Documentation   ||     (1-5★)       |    |     (1-5★)       |    |     (1-5★)       |+------------------+    +------------------+    +------------------+| Pickup/Delivery  |    | ETA updates      |    | Inspection photos|| Window accuracy  |    | Response time    |    | Clean signed eBOL|| Checkpoint timing|    | GPS/Live tracking|    | Gate Pass/Invoice|+------------------+    +------------------+    +------------------+ Каждая категория имеет четкие операционные критерии, влияющие на совокупную карточку благонадежности перевозчика (Carrier Scorecard) [3].

| Критерий оценки (Criterion) | Операционное определение платформы | Основные триггеры снижения рейтинга | Стандарт превентивного контроля диспетчерской службы |
| :--- | :--- | :--- | :--- |
| **Timeliness (Своевременность)** | Степень соблюдения временных параметров погрузки, доставки и прохождения промежуточных чекпоинтов, зафиксированных в договоре [3]. | Опоздание на погрузку или доставку без согласования свыше временного окна; нарушение 72-часового правила доставки от расчетного времени [3]. | Письменное согласование переноса окон в чате Central Dispatch и по email минимум за 4–6 часов до истечения согласованного времени прибытия [3]. |
| **Communication (Коммуникация)** | Профессионализм, оперативность реагирования и открытость перевозчика в процессе выполнения рейса [3]. | Отсутствие ответов на запросы брокера более 30 минут, отказ предоставить телефон водителя, отключение трекинга, конфликтное поведение [3]. | Ответ на входящие запросы экспедитора в течение максимум 15 минут в рабочие часы; подключение водителя к Central Dispatch App с передачей геолокации [4]. |
| **Documentation (Документооборот)** | Качество, юридическая чистота, читаемость и своевременность предоставления сопутствующих документов [3]. | Размытые фото повреждений, отсутствие подписей в графах приема/сдачи, задержка предоставления eBOL свыше 24 часов после выгрузки [3]. | Загрузка подписанного eBOL высокой четкости с детальным отчетом об инспекции в мобильное приложение в течение 2 часов после завершения рейса [3]. |

При попытке выставить оценку в 1 или 2 звезды интерфейс системы в обязательном порядке активирует требование составить развернутый текстовый комментарий с обоснованием претензии [3]. Это предотвращает необоснованное выставление негатива под воздействием эмоций и формирует текстовую доказательную базу для последующего анализа [3]. Кроме того, функционал дает возможность оценивать аннулированные заказы (Cancelled Transactions), что защищает добросовестных участников от скрытых срывов загрузок со стороны безответственных партнеров [1].

Влияние рейтинга на бизнес и встречные оценки контрагентов Рейтинговый профиль на Central Dispatch прямо конвертируется в финансовые результаты автовозного бизнеса [4]. Крупнейшие брокерские компании рынка Car Hauling используют автоматизированные интеграции между Central Dispatch и собственными TMS [4]. Эти алгоритмы ранжируют поступающие запросы от автовозов по совокупному показателю Scorecard [4].

Падение общего рейтинга ниже 98% переводит профиль перевозчика в категорию повышенного риска [4]. По статистике логистического рынка США, падение позитивного рейтинга компании со 100% до диапазона 95–97% влечет падение одобрения входящих запросов на бронирование более чем на 50%. Экспедиторы первого эшелона отклоняют заявки таких перевозчиков автоматически, перенаправляя высокомаржинальные заводские и дилерские автомобили проверенным флотам со 100% рейтингом даже при более высокой запрашиваемой ставке [4].

С другой стороны, система Transactional Ratings является строго симметричной [3]. Перевозчики обладают полным правом выставлять встречные оценки брокерам и автодилерам [4]. Оценка брокера формируется по аналогичным трем направлениям:

Timeliness (Своевременность оплаты):

Соблюдение согласованных условий выплат (QuickPay, Net 15, Net 30) [6].

Documentation (Точность описания):

Соответствие фактических характеристик ТС заявленным на платформе (точный VIN, реальные габариты, корректный статус неисправностей, предоставление рабочего Release PIN) [11].

Communication (Профессионализм экспедитора):

Доступность агентов на телефонах, помощь в решении проблем с доступом на аукционы в нештатных ситуациях [3].

Регулярное выставление объективных встречных оценок защищает рынок от неплательщиков и брокеров, публикующих заведомо ложную информацию о грузах [6].

Модерация и отложенная публикация (72-Hour Moderation & Review Window) Исторической проблемой логистических досок объявлений являлась практика «ответной мести» (Retaliatory Ratings), при которой перевозчики опасались выставлять негативные оценки недобросовестным заказчикам из-за риска получить зеркальный отрицательный балл в свой профиль [6]. Обновленная архитектура Central Dispatch устраняет эту системную уязвимость с помощью двух инструментов: динамических окон оценивания и процедуры слепого рецензирования [6].

Механика Dynamic Rating Windows Для предотвращения манипуляций со стороны брокеров платформа внедрила динамические временные рамки (Dynamic Rating Windows) [6]. Период, в течение которого перевозчик имеет право выставить оценку заказчику, больше не является фиксированным: он автоматически синхронизируется с заявленными сроками оплаты заказа (Payment Terms) [6].

Если контракт заключен на условиях отсрочки платежа (Net 30), окно выставления оценки перевозчиком открывается и сохраняет активность после наступления расчетной даты платежа [6]. Таким образом, если брокер задерживает перечисление заработанных средств, перевозчик сохраняет гарантированную техническую возможность отразить данный инцидент в рейтинге по критерию Timeliness / Payment Behavior [6].

Для всех закрытых и отмененных транзакций действует базовое платформенное окно доступности: все незаполненные оценки хранятся в разделе Pending личного кабинета ровно 60 дней [3]. По истечении этого срока техническая возможность оставить отзыв безвозвратно аннулируется [3]. В свою очередь, регламент рассмотрения споров (Rules of Engagement) устанавливает, что негативные или нейтральные отзывы должны формироваться сторонами в пределах 30 дней от даты первичного назначения заказа (Order Assignment Date), за исключением документально подтвержденных длительных отсрочек оплаты [11].

Инструмент Publish Later и 72-часовая модерация Механизм слепой публикации (Publish Later) представляет собой инструмент защиты объективности [6]. При оставлении отзыва в отношении недобросовестного партнера диспетчер активирует функцию Publish Later [6].

+------------------------------------+                                      |   Диспетчер выставляет отзыв       |                                      |    с опцией "Publish Later"        |                                      +-----------------+------------------+                                                        |                                                        v                                      +------------------------------------+                                      |  Отзыв скрыт (Blind Hold)          |                                      |  Партнер не видит оценку и текст   |                                      +-----------------+------------------+                                                        |                               +------------------------+------------------------+                               |                                                 |                               v                                                 v             +------------------------------------+            +------------------------------------+             |    Партнер отправляет свой отзыв   |            |   Истекает 14-дневный лимит        |             |       по данной транзакции         |            |      (14-day Review Window)        |             +-----------------+------------------+            +-----------------+------------------+                               |                                                 |                               +------------------------+------------------------+                                                        |                                                        v                                      +------------------------------------+                                      |   СИНХРОННАЯ ПУБЛИКАЦИЯ ОТЗЫВОВ   |                                      |    в открытом доступе профилей     |                                      +------------------------------------+ В рамках этого режима оставленная оценка и текст рецензии не отображаются в публичном профиле контрагента до наступления одного из двух событий: либо партнер выставил встречный отзыв по данной транзакции, либо истек установленный правилами 14-дневный период рецензирования (14-day Review Window) [6]. Данный порядок полностью исключает шантаж и зеркальные мстительные отзывы, поскольку контрагент не знает, какую оценку выставил перевозчик, до момента фиксации собственного мнения [6].

При возникновении разногласий платформа Central Dispatch декларирует жесткий базовый принцип:

«Once posted, Central Dispatch ratings and reviews cannot be changed» (После момента публикации отзывы не подлежат редактированию или отзыву сторонами) [23]. Это накладывает особую ответственность на этап досудебного урегулирования (Amicable Resolution) [3]. Если перевозчик допустил объективную задержку или технический сбой, диспетчер обязан перехватить конфликт до публикации отзыва, связавшись с руководством брокерской компании напрямую [3]. Стандартной практикой является предоставление коммерческой компенсации (скидка от $50 до $200 от утвержденного тарифа или компенсация затрат на детейлинг) в обмен на письменное соглашение сторон об отсутствии претензий и отказе от выставления негативного рейтинга на платформе.

В случаях, когда негативный отзыв все же стал публичным, компания имеет законное право опубликовать официальный ответ (Public Reply) [3]. Каждый направленный ответ отправляется на пре-модерацию в службу комплаенса Central Dispatch на 72 часа (72-Hour Review Period) [3]. В течение этого срока модераторы проверяют текст на отсутствие нарушений Content Guidelines: запрещены прямые оскорбления, ненормативная лексика, публикация персональных конфиденциальных данных физических лиц (PII: номера личных мобильных телефонов, домашние адреса частных клиентов) [3]. После прохождения 72-часовой верификации ответ крепится к телу отзыва, демонстрируя сообществу профессиональный подход компании к спорным ситуациям [3].

Протокол оспаривания негативных отзывов (Rating Dispute Protocol) Если брокер злоупотребляет платформенными инструментами и размещает необоснованный негативный рейтинг в нарушение правил биржи, диспетчерская служба запускает официальный протокол арбитража на основании официального регламента — CentralDispatch Ratings Rules of Engagement [11].

Законные основания для удаления негативного отзыва администрацией Central Dispatch Несмотря на то что Central Dispatch не выступает третейским судьей в финансовых разногласиях сторон, администрация безоговорочно удаляет любые оценки, выставленные с нарушением зафиксированных Правил взаимодействия [11].

Основание для удаления отзыва (Dispute Grounds) Статья регламента (Rules of Engagement) Фактические обстоятельства инцидента Доказательная база перевозчика Действие арбитража Central Dispatch Шантаж оценкой (Rating Extortion) Section 7.a: «Manipulation of ratings / Inauthentic content / Bad faith» [11] Брокер требует снижения утвержденной ставки или выполнения бесплатных погрузочных работ под прямой угрозой выставления негативного отзыва в профиль.

Скриншоты СМС-сообщений, email-переписка или аудиозапись разговора с требованием уступок под угрозой низкого рейтинга.

Немедленное удаление отзыва; блокировка или вынесение официального предупреждения аккаунту брокера [11].

Доказанный срыв по вине брокера (Dry Run / Cancellation) Section 4.b: «Shipper failure to communicate changes / cancel terms» [11] Автовоз прибыл на погрузку вовремя, но автомобиль отсутствует на площадке, продан дилером стороннему лицу либо не имеет оплаченного Gate Pass. Брокер аннулирует рейс и ставит единицу перевозчику.

Данные ELD/GPS, фото ворот терминала с геолокацией, телефонный лог безуспешных попыток связаться с брокером, инвойс за холостой пробег (Dry Run Invoice) [11].

Полное удаление отзыва как необоснованного и не соответствующего фактам [11].

Недостоверные данные о состоянии ТС (False Condition) Section 4.a: «Failure to meet mutually agreed terms: Condition of vehicle» [11] В листинге и Rate Con указано состояние Runs & Drives, по факту прибытия авто полностью разбито, колеса заблокированы, требуется лебедка/погрузчик. Перевозчик отказался от погрузки без доплаты.

Скан первоначального Rate Con, детальные фотографии ТС на локации, Condition Report аукциона с фиксацией дефектов [11].

Удаление отзыва: брокер нарушил фундаментальное контрактное условие сделки [11].

Нарушение 30-дневного регламентного срока Section 8: «Submission of Negative/Neutral ratings within 30 days of assignment» [11] Экспедитор размещает отрицательный отзыв спустя 35–45 дней с момента выдачи заказа, мотивируя это запоздалыми претензиями своего заказчика.

Сверка даты выдачи заказа в системе Central Dispatch и даты фактического добавления отзыва брокером [11].

Безусловное техническое удаление отзыва без рассмотрения сопутствующих обстоятельств [11].

Отсутствие транзакции внутри платформы Section 1.b: «Rating a Member without direct transaction originating on CD» [11] Отрицательный отзыв оставлен брокером, с которым велись предварительные переговоры, но контракт не оформлялся и заказ не имел статуса Dispatched на Central Dispatch.

Выписка из реестра заказов биржи, подтверждающая отсутствие зарегистрированного Order ID между сторонами [11].

Немедленное удаление отзыва; штрафные санкции в адрес заявителя за спам [11].

Доказательный пакет для арбитража (Dispute Evidence Package) и процедура эскалации Процедура арбитража строится на состязательности сторон [11]. При подаче апелляции компанией, получившей негативную оценку (Rated Member), система направляет уведомление брокеру (Rating Member) с требованием предоставить документальные обоснования претензии [11].

Регламент фиксирует ключевую процедурную норму:

«The company submitting the rating will be allowed to supply their own documentation to support the rating issued. Failure to escalate a rating with or without documentation will result in the rating's automatic removal» [11]. Если брокер не предоставляет юридически значимых доказательств в ответ на открытый диспут, негативный отзыв удаляется арбитражной системой автоматически [11].

Формируемый диспетчером пакет доказательств (Dispute Evidence Package) включает следующие обязательные компоненты:

Телематические логи сертифицированного ELD:

Поминутная выгрузка данных бортового регистратора (KeepTruckin/Motive, Samsara и др.) с фиксацией координат трака, временных отметок прибытия на геозону объекта (Geofence Arrival/Departure) и времени ожидания [14].

Электронный коносамент (eBOL):

Документ из специализированной системы (Super Dispatch, RunBuggy), содержащий фотофиксацию высокого разрешения всех кузовных панелей в момент погрузки, временные штампы и подписи передающей и принимающей сторон [3].

Коммуникационные протоколы:

Заверенная детализация телефонных звонков от оператора связи, подтверждающая попытки диспетчера уведомить брокера о простое, а также полные скриншоты переписки без обрезки заголовков и таймстемпов [3].

Вспомогательные транспортные документы:

Официальные акты осмотра терминалов (Vehicle Condition Reports), квитанции за въезд на аукционные площадки, счета за вызов стороннего эвакуатора/погрузчика.

Подача документов производится через платформенную форму связи комплаенс-отдела (Central Dispatch Support / Rating Appeals) либо посредством прямого обращения в департамент модерации по телефонам поддержки 1-800-928-7869 или 855-COX-AUTO [6].

Официальное обращение в арбитраж Central Dispatch SUBJECT:

FORMAL RATING DISPUTE & REMOVAL REQUEST | MC# [Указать MC перевозчика] | Order ID: [Указать ID заказа] ATTN:

Central Dispatch Rating Appeals & Compliance Department This is a formal dispute submitted by [Юридическое наименование перевозчика] (MC# [Номер MC], USDOT# [Номер USDOT]) regarding an illegitimate, retaliatory negative rating posted by [Наименование брокера] (Central Dispatch Member ID: [ID брокера]) in relation to Order ID: [Номер заказа], assigned on [Дата назначения заказа].

LEGAL GROUNDS FOR REMOVAL:

Violation of the Central Dispatch Ratings Rules of Engagement — Specifically Section 4(a) (Failure to meet agreed terms regarding vehicle condition), Section 4(b) (Shipper communication failures), and Section 7(a) (Ratings manipulation and extortion).

STATEMENT OF FACTS:

On [Дата заключения сделки], our company accepted Order ID: [Номер заказа] with the contracted Rate Confirmation explicitly defining the cargo as one operable vehicle ("Runs & Drives").

On [Дата прибытия на погрузку] at [Точное время прибытия] EST, our driver arrived at the pickup location within the agreed timeframe, verified by certified ELD telematics (Exhibit B).

Upon inspection, the vehicle was determined to be completely inoperable, with deployed airbags, severe front-axle damage, and locked brakes, precluding safe manual winching onto an open multi-car stinger trailer (Exhibit C).

Our dispatch team immediately contacted the broker via phone and email at [Время отправки запроса], requesting an updated Rate Confirmation with an Inop/Winch surcharge of $[Сумма доплаты] or authorization to arrange an on-site forklift.

The broker representative refused to modify the rate confirmation and explicitly stated via text/email that if our driver did not load the inoperable vehicle immediately at the original rate, they would "leave a 1-star review to damage your carrier rating" (Exhibit D).

Due to severe DOT safety and cargo securement regulations, our driver could not perform this unauthorized operation. The load was subsequently cancelled. The broker posted a 1-star negative rating citing "Carrier dropped load / Unprofessional conduct." SUBMITTED EVIDENCE PACKAGE (EXHIBITS A–D):

Exhibit A:

Original countersigned Rate Confirmation detailing VIN and operational status.

Exhibit B:

Certified ELD GPS time-stamped log showing vehicle arrival and dwell time inside the facility geofence.

Exhibit C:

High-resolution on-site photographs and lot condition report proving inoperability.

Exhibit D:

Unedited digital communications displaying timestamped notifications and direct broker rating extortion statements.

Pursuant to Section 6(c) and Section 7 of the CentralDispatch Ratings Rules of Engagement, ratings lacking factual validity, demonstrating manipulative intent, or submitted following shipper contract breaches must be purged. We formally request the immediate removal of this rating from our company scorecard.

Respectfully submitted, [Имя и Фамилия специалиста] Head of Safety & Compliance | [Наименование компании] Direct Line: [Телефон] | Corporate Email: [Email] Чек-лист диспетчера по защите рейтинга (Rating Protection Checklist) Для систематической защиты 100% рейтинга диспетчерский персонал обязан внедрить в ежедневную работу сквозной 8-этапный регламент управления рисками.

Этап рейса (Operational Phase) Контрольный шаг алгоритма Обязательное действие диспетчера Фиксируемый артефакт (Compliance Artifact) Предотвращаемый операционный риск

## 1. Предварительный аудит (Pre-Booking)

Проверка благонадежности заказчика (Scorecard Vetting) [4].

Анализ профиля брокера на Central Dispatch: проверка рейтинга платежной дисциплины, времени жизни аккаунта и отзывов коллег о необоснованных отменах [4].

Скриншот профиля брокера с метриками надежности в архиве TMS.

Срыв оплаты, взаимодействие с мошенническими фирмами (Double Brokering) [4].

## 2. Контрактная сверка (Rate Con Audit)

Аудит условий соглашения и статуса груза [24].

Сверка VIN, реальных габаритов (наличие багажников, лифтов кузова), статуса Run/Inop, адресов и наличия штрафов за опоздание (Detention/TONU clauses) [5].

Подписанный Rate Con с внесенными и заверенными правками по ставке и окнам [5].

Неоплачиваемый холостой пробег, отказ в доплате за погрузку неисправного ТС [11].

## 3. Предрейсовый инструктаж (Driver Briefing)

Контроль готовности оборудования и разрешений [12].

Проверка наличия у водителя спецремней (Over-the-tire Straps), рабочей лебедки, высотомера (Height Stick), активного приложения Central Dispatch App [14].

Отметка о прохождении предрейсового инструктажа в TMS автопарка.

Повреждение подвески перевозимых авто, штрафы за негабарит по высоте, срыв погрузки [12].

## 4. Отслеживание транзита (Transit Tracking)

Непрерывный мониторинг и упреждающая связь [3].

Контроль включения водителем функции Real-Time Tracking; направление брокеру апдейтов по расчетному времени прибытия (ETA) каждые 24 часа или при риске опоздания свыше 2 часов [3].

Лог переписки и системные отметки отправки геопозиции в Central Dispatch [3].

Претензии по категории Communication; необоснованные штрафы за нарушение дедлайнов [3].

## 5. Погрузочная инспекция (Pickup Inspection)

Тотальная фотофиксация и электронный акт (eBOL) [3].

Проведение кругового осмотра ТС: съемка минимум 10–12 детальных фотографий (пороги, бамперы, крыша, стекла, салон, одометр); фиксация подписи грузоотправителя в eBOL [8].

Завершенный электронный акт eBOL с временным штампом и цифровой подписью отправителя [3].

Ложные претензии по ранее существовавшим кузовным повреждениям (Damage Claims) [3].

## 6. Сдача груза (Delivery Sign-Off)

Финальная сдача и подписание POD [3].

Повторный осмотр автомобиля в присутствии получателя; получение подписи с четкой расшифровкой фамилии; при отказе от подписи — немедленный звонок брокеру [3].

Полностью подписанный акт передачи ТС (Proof of Delivery / Signed POD) [3].

Заявления о краже ключей, повреждении авто при разгрузке или удержании ТС [11].

## 7. Закрытие заказа (Invoicing & Status)

Обновление статуса на CD и биллинг [4].

Перевод заказа в статус Delivered на сайте Central Dispatch в течение 60 минут после сдачи; прикрепление читаемого eBOL и инвойса со всеми согласованными доп. расходами [4].

Зафиксированный в системе статус закрытия с прикрепленным пакетом документов [4].

Задержка оплаты экспедитором, претензии по критерию Documentation [3].

## 8. Стратегическое оценивание (Rating Strategy)

Выставление отзыва с чекбоксом «Publish Later» [6].

Оценка работы брокера по трем критериям с обязательным выбором режима Publish Later; при возникновении спора — оперативное решение через Amicable Resolution до публикации [6].

Зарегистрированная встречная оценка в разделе Pending Ratings аккаунта [3].

Защита от получения ответных мстительных отзывов и поддержание 100% Scorecard [6].

Заключение Поддержание максимального рейтинга на платформе Central Dispatch выступает прямым отражением институциональной зрелости автотранспортной компании. На современном рынке Car Hauling репутационный статус напрямую диктует финансовую устойчивость бизнеса: высокий транзакционный рейтинг гарантирует стабильный приоритетный доступ к заказам ведущих брокеров, усиливает позиции перевозчика в переговорах по тарифам за милю и формирует надежный правовой барьер против недобросовестных манипуляций со стороны контрагентов [4]. Системное соблюдение требований комплаенса, дисциплина документооборота и жесткое применение арбитражных процедур обеспечивают долгосрочную безопасность и высокую рентабельность автопарка [6].

Works cited Central Dispatch's New Ratings System Drawing Many User Reviews, https://www.vehicleremarket.com/news/central-dispatchs-new-ratings-system-drawing-many-user-reviews https://www.vehicleremarket.com/news/central-dispatchs-new-ratings-system-drawing-many-user-reviews Transactional Ratings - Press Releases | Manheim Newsroom, https://press.manheim.com/2023-06-29-Central-Dispatchs-New-Transactional-Ratings-Attracts-Over-500,000-Ratings-in-First-Months-Most-Requested-Feature-Just-Added https://press.manheim.com/2023-06-29-Central-Dispatchs-New-Transactional-Ratings-Attracts-Over-500,000-Ratings-in-First-Months-Most-Requested-Feature-Just-Added Transactional Ratings Overview - Central Dispatch, https://www.centraldispatch.com/resources/transactional-ratings-overview https://www.centraldispatch.com/resources/transactional-ratings-overview Getting Started Archives - Central Dispatch, https://www.centraldispatch.com/resource-topic/getting-started https://www.centraldispatch.com/resource-topic/getting-started What Is the Central Dispatch Load Board? - NexGen Auto Transport, https://nexgenautotransport.com/what-is-the-central-dispatch-load-board/https://nexgenautotransport.com/what-is-the-central-dispatch-load-board/Auto Transportation's Most Reliable Rating System - Central Dispatch, https://www.centraldispatch.com/transactional-ratings https://www.centraldispatch.com/transactional-ratings How We Vet Carriers for Insurance, Monitoring, and Compliance, https://www.autohaulerexchange.com/blog/how-we-vet-carriers-for-insurance-monitoring-and-compliance https://www.autohaulerexchange.com/blog/how-we-vet-carriers-for-insurance-monitoring-and-compliance How to start a car transport business: 10 steps and costs (2026) - JIM, https://www.jim.com/blog/how-to-start-a-car-transport-business https://www.jim.com/blog/how-to-start-a-car-transport-business Car Hauler Insurance Florida | Auto Hauler & On-Hook Cargo, https://floridatransportationinsurance.com/car-hauler-insurance-florida https://floridatransportationinsurance.com/car-hauler-insurance-florida On-Hook & Cargo Insurance Question: r/Hookit - Reddit, https://www.reddit.com/r/Hookit/comments/1nlxh6v/onhook_cargo_insurance_question/https://www.reddit.com/r/Hookit/comments/1nlxh6v/onhook_cargo_insurance_question/Rules of Engagement – CentralDispatch Ratings Management, https://site.centraldispatch.com/images/services/Central-Dispatch-Ratings-Rules-of-Engagement.pdf https://site.centraldispatch.com/images/services/Central-Dispatch-Ratings-Rules-of-Engagement.pdf Complete Guide to Starting a Car Hauling Business: From Dream to, https://freightandauto.com/blog/complete-guide-to-starting-a-car-hauling-business https://freightandauto.com/blog/complete-guide-to-starting-a-car-hauling-business How Much Can You Make Car Hauling? - Trucking42, https://trucking42.com/blog/how-much-can-you-make-car-hauling/https://trucking42.com/blog/how-much-can-you-make-car-hauling/How to Start a Car Hauling Business in 8 Steps | ZenBusiness, https://www.zenbusiness.com/start-a-business/transportation/car-hauling/https://www.zenbusiness.com/start-a-business/transportation/car-hauling/Car Hauling Tips: A Guide for Owner-Operators - Dispatch Republic, https://dispatchrepublic.com/car-hauling-tips-a-guide-for-owner-operators/https://dispatchrepublic.com/car-hauling-tips-a-guide-for-owner-operators/See how you can take control - Central Dispatch, https://www.centraldispatch.com/features https://www.centraldispatch.com/features Never miss a load with notifications! - Central Dispatch, https://www.centraldispatch.com/resources/carrier-notifications-for-saved-searches https://www.centraldispatch.com/resources/carrier-notifications-for-saved-searches How to Manage Listings - Central Dispatch, https://www.centraldispatch.com/resources/how-to-manage-listings https://www.centraldispatch.com/resources/how-to-manage-listings Carriers Archives - Central Dispatch, https://www.centraldispatch.com/resource-audience/carriers https://www.centraldispatch.com/resource-audience/carriers Central Dispatch Highlights – Sep 30, 2026, https://www.centraldispatch.com/resources/central-dispatch-highlights-september-2026 https://www.centraldispatch.com/resources/central-dispatch-highlights-september-2026 Shippers Archives - Central Dispatch, https://www.centraldispatch.com/resource-audience/shippers https://www.centraldispatch.com/resource-audience/shippers Terms of Use - Central Dispatch, https://www.centraldispatch.com/terms-of-use https://www.centraldispatch.com/terms-of-use Tips for Rating & Reviewing Transactions - Central Dispatch, https://www.centraldispatch.com/resources/tips-for-rating-reviewing-transactions https://www.centraldispatch.com/resources/tips-for-rating-reviewing-transactions Central Dispatch Insurance Overview | PDF | Common Carrier - Scribd, https://www.scribd.com/document/573936178/1649106007137-21179-DispatchSheetOrder https://www.scribd.com/document/573936178/1649106007137-21179-DispatchSheetOrder How-To Archives - Central Dispatch, https://www.centraldispatch.com/resource-topic/how-to https://www.centraldispatch.com/resource-topic/how-to NEW: Ratings now reflect actual payment behavior - Central Dispatch, https://www.centraldispatch.com/resources/transactional-ratings-dynamic-rating-window https://www.centraldispatch.com/resources/transactional-ratings-dynamic-rating-window Real-Time Tracking - Central Dispatch, https://www.centraldispatch.com/features/real-time-tracking https://www.centraldispatch.com/features/real-time-tracking Find Reliable Partners with Transactional Ratings - Central Dispatch, https://www.centraldispatch.com/resources/find-reliable-partners-with-transaction-ratings https://www.centraldispatch.com/resources/find-reliable-partners-with-transaction-ratings What Trucking Insurance Does My Company Need?, https://blog.central-insurance.com/trucking-insurance/https://blog.central-insurance.com/trucking-insurance/Contact Us - Central Dispatch, https://www.centraldispatch.com/contact-us https://www.centraldispatch.com/contact-us About Us - Central Dispatch, https://www.centraldispatch.com/about-us https://www.centraldispatch.com/about-us How to Add Invoice Expenses in the Mobile App - Central Dispatch, https://www.centraldispatch.com/resources/carrier-add-expenses-mobile-app https://www.centraldispatch.com/resources/carrier-add-expenses-mobile-app
