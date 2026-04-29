from dataclasses import dataclass, field


@dataclass
class Question:
    id: str
    text: str
    block: str          # "personality", "expertise", "product"
    subblock: str       # human-readable subblock name
    follow_ups: list[str] = field(default_factory=list)


# ══════════════════════════════════════════════════════════════
# БЛОК 1: РАСПАКОВКА ЛИЧНОСТИ (100 вопросов)
# ══════════════════════════════════════════════════════════════

PERSONALITY_QUESTIONS: list[Question] = [
    # ── 1.1 Свободное время и увлечения ──
    Question("p_01", "Чем вы любите заниматься в свободное время?", "personality", "hobbies"),
    Question("p_02", "Какое место вы посетили и что из этого вынесли?", "personality", "hobbies"),
    Question("p_03", "Как вы проводите время с семьей или друзьями?", "personality", "hobbies"),
    Question("p_04", "Какие упражнения входят в вашу ежедневную рутину?", "personality", "hobbies"),
    Question("p_05", "Что вас увлекает в вашем хобби?", "personality", "hobbies"),
    Question("p_06", "Какое ваше любимое блюдо для приготовления?", "personality", "hobbies"),
    Question("p_07", "Что вы обычно делаете, чтобы расслабиться?", "personality", "hobbies"),
    Question("p_08", "В чём заключается ваш идеальный отдых?", "personality", "hobbies"),
    Question("p_09", "Какое ваше любимое место в городе, где вы живёте?", "personality", "hobbies"),
    Question("p_10", "Как вы отмечаете свой день рождения?", "personality", "hobbies"),
    Question("p_11", "Какой предмет в вашем доме имеет для вас особое значение?", "personality", "hobbies"),

    # ── 1.2 Личные качества и ценности ──
    Question("p_12", "Какое ваше самое сильное личное качество?", "personality", "values"),
    Question("p_13", "Что для вас означает креативность?", "personality", "values"),
    Question("p_14", "Какой ваш любимый способ общения: личные встречи, телефонные звонки, социальные сети?", "personality", "values"),
    Question("p_15", "Какое ваше любимое семейное воспоминание?", "personality", "values"),
    Question("p_16", "Что для вас означает семья?", "personality", "values"),
    Question("p_17", "Какой ваш самый любимый праздник в году?", "personality", "values"),
    Question("p_18", "Что бы вы хотели изменить в себе?", "personality", "values"),
    Question("p_19", "Есть ли у вас скрытые таланты?", "personality", "values"),
    Question("p_20", "Что вы цените в культуре вашей страны?", "personality", "values"),
    Question("p_21", "Какой самый важный урок вы усвоили в жизни?", "personality", "values"),
    Question("p_22", "Есть ли что-то, что вы хотели бы изменить в обществе?", "personality", "values"),
    Question("p_23", "Что для вас означает дом?", "personality", "values"),
    Question("p_24", "Что для вас значит истинная дружба?", "personality", "values"),
    Question("p_25", "Есть ли у вас любимая традиция?", "personality", "values"),
    Question("p_26", "Что вас заставляет чувствовать себя живым?", "personality", "values"),
    Question("p_27", "Какой совет вы бы дали своему младшему Я?", "personality", "values"),
    Question("p_28", "Как вы относитесь к моде и стилю?", "personality", "values"),
    Question("p_29", "Какой вы человек? Опишите свои личностные качества.", "personality", "values"),
    Question("p_30", "Что о вас говорят другие?", "personality", "values"),

    # ── 1.3 Семья и окружение ──
    Question("p_31", "Кто из вашей семьи повлиял на вас больше всего?", "personality", "family"),
    Question("p_32", "Есть ли у вас в окружении авторитетные для вас люди?", "personality", "family"),
    Question("p_33", "Какие положительные качества вы взяли от родителей?", "personality", "family"),
    Question("p_34", "Какие отрицательные качества вы взяли от родителей?", "personality", "family"),
    Question("p_35", "Есть ли у вас домашнее животное?", "personality", "family"),
    Question("p_36", "Кем вы мечтали стать в детстве?", "personality", "family"),
    Question("p_37", "Какой основной страх вы испытывали, будучи маленьким ребенком?", "personality", "family"),
    Question("p_38", "С каким супергероем вы себя ассоциируете?", "personality", "family"),
    Question("p_39", "Любите ли вы маленьких детей?", "personality", "family"),
    Question("p_40", "Насколько эмоционально вы переживаете события при просмотре фильмов?", "personality", "family"),
    Question("p_41", "Что может вас рассмешить до слёз?", "personality", "family"),
    Question("p_42", "У вас большое окружение или маленькое?", "personality", "family"),
    Question("p_43", "Какой ваш самый близкий друг?", "personality", "family"),
    Question("p_44", "Как вы проводите время с друзьями?", "personality", "family"),
    Question("p_45", "Как вы выбираете партнёра для жизни?", "personality", "family"),

    # ── 1.4 Образ жизни и привычки ──
    Question("p_46", "Как вы организуете свой рабочий день?", "personality", "lifestyle"),
    Question("p_47", "Есть ли у вас страх просить помощь?", "personality", "lifestyle"),
    Question("p_48", "Какой последний риск вы на себя взяли?", "personality", "lifestyle"),
    Question("p_49", "Какое самое смелое решение вы когда-либо принимали?", "personality", "lifestyle"),
    Question("p_50", "Какой последний фильм или сериал вас впечатлил?", "personality", "lifestyle"),
    Question("p_51", "Какие изменения вы заметили в себе за последние годы?", "personality", "lifestyle"),
    Question("p_52", "Как вы относитесь к путешествиям?", "personality", "lifestyle"),
    Question("p_53", "Какие темы вас интересуют в новостях?", "personality", "lifestyle"),
    Question("p_54", "Как вы относитесь к спорту?", "personality", "lifestyle"),
    Question("p_55", "Какие у вас есть привычки?", "personality", "lifestyle"),
    Question("p_56", "Как вы относитесь к здоровому образу жизни?", "personality", "lifestyle"),
    Question("p_57", "Какие у вас кулинарные предпочтения?", "personality", "lifestyle"),
    Question("p_58", "Что вас мотивирует учиться новому?", "personality", "lifestyle"),
    Question("p_59", "Какие факты о вас могут удивить других?", "personality", "lifestyle"),
    Question("p_60", "Что вы цените в путешествиях?", "personality", "lifestyle"),
    Question("p_61", "Как вы относитесь к различным культурам?", "personality", "lifestyle"),
    Question("p_62", "Какие у вас есть увлечения?", "personality", "lifestyle"),
    Question("p_63", "Как вы относитесь к экологии?", "personality", "lifestyle"),
    Question("p_64", "Какие у вас мечты на будущее?", "personality", "lifestyle"),
    Question("p_65", "Какие события оказали значительное влияние на вашу жизнь?", "personality", "lifestyle"),

    # ── 1.5 Саморазвитие и философия ──
    Question("p_66", "Как вы относитесь к работе и карьере?", "personality", "philosophy"),
    Question("p_67", "Какие книги оказали на вас влияние?", "personality", "philosophy"),
    Question("p_68", "Какие фильмы или сериалы вы любите?", "personality", "philosophy"),
    Question("p_69", "Как вы относитесь к искусству?", "personality", "philosophy"),
    Question("p_70", "Что для вас означает успех?", "personality", "philosophy"),
    Question("p_71", "Как вы относитесь к деньгам и финансам?", "personality", "philosophy"),
    Question("p_72", "Какие советы вы бы дали молодому поколению?", "personality", "philosophy"),
    Question("p_73", "Что для вас означает счастье?", "personality", "philosophy"),
    Question("p_74", "Что бы вы предпочли — изучить теорию или сделать сразу практику?", "personality", "philosophy"),
    Question("p_75", "Как вы выбираете работу, на что опираетесь при выборе?", "personality", "philosophy"),
    Question("p_76", "Есть ли у вас личные традиции и ритуалы?", "personality", "philosophy"),
    Question("p_77", "Как вы покупаете — эмоционально или вдумчиво?", "personality", "philosophy"),
    Question("p_78", "Вам легко достаются деньги, подарки?", "personality", "philosophy"),
    Question("p_79", "Как вы относитесь к различным правилам?", "personality", "philosophy"),
    Question("p_80", "Какую одежду вы носите?", "personality", "philosophy"),

    # ── 1.6 Глубинные вопросы ──
    Question("p_81", "В каких цветах вы бы хотели иметь комнату/дом?", "personality", "deep"),
    Question("p_82", "Какой ваш любимый цвет?", "personality", "deep"),
    Question("p_83", "Вы верующий человек?", "personality", "deep"),
    Question("p_84", "Как вы относитесь к истории своей страны?", "personality", "deep"),
    Question("p_85", "Насколько вы проявляете эмпатию по отношению к другим людям?", "personality", "deep"),
    Question("p_86", "За что вам стыдно больше всего?", "personality", "deep"),
    Question("p_87", "А чем вы больше всего гордитесь?", "personality", "deep"),
    Question("p_88", "Любите ли вы ухаживать за своим телом?", "personality", "deep"),
    Question("p_89", "Что для вас важно в других людях?", "personality", "deep"),
    Question("p_90", "Какую книгу или курс вы недавно прошли и рекомендуете?", "personality", "deep"),
    Question("p_91", "Какая цитата недавно вдохновила вас?", "personality", "deep"),
    Question("p_92", "Как вы относитесь к обучению и самообразованию?", "personality", "deep"),
    Question("p_93", "Что вам нравится больше всего в вашем городе/стране?", "personality", "deep"),
    Question("p_94", "Какой ваш любимый вид спорта?", "personality", "deep"),
    Question("p_95", "Как вы относитесь к благотворительности?", "personality", "deep"),
    Question("p_96", "Как вы относитесь к праздникам и как их отмечаете?", "personality", "deep"),
    Question("p_97", "Есть ли у вас любимое место для отдыха?", "personality", "deep"),
    Question("p_98", "Какой совет вы бы дали начинающим в вашей профессии?", "personality", "deep"),
    Question("p_99", "Что мотивирует вас каждое утро?", "personality", "deep"),
    Question("p_100", "Как вы относитесь к ошибкам в работе?", "personality", "deep"),
]

# ══════════════════════════════════════════════════════════════
# БЛОК 2: РАСПАКОВКА ЭКСПЕРТНОСТИ (100 вопросов)
# ══════════════════════════════════════════════════════════════

EXPERTISE_QUESTIONS: list[Question] = [
    # ── 2.1 Фундамент экспертности ──
    Question("e_01", "Что такое экспертность, по вашему мнению?", "expertise", "foundation"),
    Question("e_02", "Почему экспертность важна?", "expertise", "foundation"),
    Question("e_03", "Какие у вас уникальные навыки и знания?", "expertise", "foundation"),
    Question("e_04", "Как вы можете применить свою экспертность?", "expertise", "foundation"),
    Question("e_05", "Какие ценности и убеждения определяют вашу экспертность?", "expertise", "foundation"),
    Question("e_06", "Как вы можете поделиться своей эксперностью с другими?", "expertise", "foundation"),
    Question("e_07", "В каких организациях обучают по вашей тематике? У кого вы учились?", "expertise", "foundation"),
    Question("e_08", "Где или у кого ваша экспертность реализована на топовом уровне?", "expertise", "foundation"),
    Question("e_09", "Кого из лидеров рынка вы можете привести в пример? В чём секрет их успеха?", "expertise", "foundation"),
    Question("e_10", "Можете ли вы сказать, как проходила эволюция данной темы?", "expertise", "foundation"),

    # ── 2.2 Путь и развитие ──
    Question("e_11", "Какое будущее вы видите в этой сфере в дальнейшем развитии?", "expertise", "journey"),
    Question("e_12", "А как раньше делали? А как сейчас делают? А как будут делать?", "expertise", "journey"),
    Question("e_13", "Вспомните, как вы развивались 3 года назад, какие действия совершали?", "expertise", "journey"),
    Question("e_14", "Почему вы выбрали данную сферу?", "expertise", "journey"),
    Question("e_15", "Как вы пришли к данному уровню знаний в своей сфере?", "expertise", "journey"),
    Question("e_16", "Какие навыки нужно иметь, чтобы стать лидером рынка в вашей нише?", "expertise", "journey"),
    Question("e_17", "Какие навыки необходимы, чтобы иметь возможность получать такие же результаты, как у вас сейчас?", "expertise", "journey"),
    Question("e_18", "Если человек — ноль в этом, но очень хочет, то с чего ему надо начать?", "expertise", "journey"),
    Question("e_19", "Можете ли вы расписать путь роста профессионализма в этой теме по фазам?", "expertise", "journey"),
    Question("e_20", "Каких компетенций вам не хватало ранее?", "expertise", "journey"),

    # ── 2.3 Источники и события ──
    Question("e_21", "Можете ли вы порекомендовать дополнительные источники информации (книги, фильмы, видео, специалисты, учителя, коучи, тренеры)?", "expertise", "sources"),
    Question("e_22", "Какие знаковые события произошли в этой сфере, которые имеют значение?", "expertise", "sources"),
    Question("e_23", "Какие события в вашей жизни повлияли на ваш выбор этой сферы?", "expertise", "sources"),
    Question("e_24", "С чем из того, что сейчас происходит на рынке и что делают ваши коллеги, вы не согласны?", "expertise", "sources"),
    Question("e_25", "Какие тренды вы наблюдаете?", "expertise", "sources"),

    # ── 2.4 Инструменты и цифры ──
    Question("e_26", "Какое оборудование для вашей сферы необходимо?", "expertise", "tools"),
    Question("e_27", "Используются ли какие-то специфические материалы, гаджеты или оборудование?", "expertise", "tools"),
    Question("e_28", "Какие произошли изменения за годы работы в вашей сфере, если измерить показателями? (начинали с таких-то сумм, рост был такой, было-стало)", "expertise", "tools"),
    Question("e_29", "Можете ли вы описать ваш уровень профессионализма на языке цифр? (деньги, количество людей, показатели эффективности)", "expertise", "tools"),

    # ── 2.5 Ошибки и уроки ──
    Question("e_30", "Где вы ошибались?", "expertise", "mistakes"),
    Question("e_31", "В чём ошибается большинство других?", "expertise", "mistakes"),
    Question("e_32", "К каким последствиям приводят ошибки?", "expertise", "mistakes"),
    Question("e_33", "Что является истинной причиной допущенных ошибок?", "expertise", "mistakes"),
    Question("e_34", "Какие эмоции и чувства вы в себе наблюдаете в связи с деятельностью в выбранной сфере?", "expertise", "mistakes"),
    Question("e_35", "Что было самым сложным психологически для вас, чтобы начать расти в выбранной сфере?", "expertise", "mistakes"),
    Question("e_36", "Что вызывало удивление или восторг у вас или у окружающих людей относительно вас?", "expertise", "mistakes"),

    # ── 2.6 Лайфхаки и подводные камни ──
    Question("e_37", "Как можно получить быстрый положительный результат в вашей сфере быстрее? На чём можно сэкономить время?", "expertise", "hacks"),
    Question("e_38", "Какие есть неочевидные тонкости и нюансы, которые большинство не знает и которые обеспечивают сверхрезультат?", "expertise", "hacks"),
    Question("e_39", "Как можно получить требуемый результат в вашей сфере легче и проще?", "expertise", "hacks"),
    Question("e_40", "К каким подводным камням, опасностям и рискам себя необходимо подготовить, начиная практиковать в вашей сфере?", "expertise", "hacks"),
    Question("e_41", "От каких негативных последствий вы можете предостеречь людей, которые могут возникнуть в силу их неопытности?", "expertise", "hacks"),
    Question("e_42", "Что в вашем деле самое сложное? Что самое простое?", "expertise", "hacks"),

    # ── 2.7 Клиенты и рынок ──
    Question("e_43", "С какими вопросами к вам обращаются чаще всего?", "expertise", "market"),
    Question("e_44", "Какие ещё сферы вы рассматривали, прежде чем остановились на этой?", "expertise", "market"),
    Question("e_45", "В чём ваше преимущество перед конкурентами?", "expertise", "market"),
    Question("e_46", "Кто является ядром вашей целевой аудитории?", "expertise", "market"),
    Question("e_47", "Кто основная масса вашей целевой аудитории? Опишите их.", "expertise", "market"),
    Question("e_48", "Какими качествами вы должны обладать, чтобы вас считали лучшим экспертом вашей области?", "expertise", "market"),
    Question("e_49", "Есть ли какие-то особенности внешнего вида у экспертов вашей области?", "expertise", "market"),
    Question("e_50", "Есть ли какие-то особенности цветовых решений у экспертов вашей области?", "expertise", "market"),

    # ── 2.8 Миссия и видение ──
    Question("e_51", "Какие три сферы для дальнейшего развития вам необходимы сейчас?", "expertise", "mission"),
    Question("e_52", "Какая у вас экспертная миссия?", "expertise", "mission"),
    Question("e_53", "Какой результат означает для вас пик вашей карьеры?", "expertise", "mission"),
    Question("e_54", "Какой ваш самый идеальный рабочий день?", "expertise", "mission"),
    Question("e_55", "Есть ли у вас собственная методика? Если да, то в чём её особенность?", "expertise", "mission"),
    Question("e_56", "Какими артефактами вы можете подтвердить вашу экспертность? (дипломы, сертификаты, кейсы, отзывы)", "expertise", "mission"),

    # ── 2.9 Работа и процессы ──
    Question("e_57", "Кого вы считаете своими прямыми конкурентами и почему?", "expertise", "work"),
    Question("e_58", "Какие сферы жизни вы считаете главными на данный момент?", "expertise", "work"),
    Question("e_59", "Какими навыками вы обладаете?", "expertise", "work"),
    Question("e_60", "Какие виды деятельности вы уже освоили?", "expertise", "work"),
    Question("e_61", "Есть ли у вас коллеги/команда? Они вам нравятся или вызывают раздражение?", "expertise", "work"),
    Question("e_62", "Опишите ваш процесс работы, из чего он состоит?", "expertise", "work"),
    Question("e_63", "Что для вас означает качество?", "expertise", "work"),
    Question("e_64", "Как вы отдыхаете и как часто?", "expertise", "work"),
    Question("e_65", "Каких результатов достигали ваши прошлые клиенты? Есть ли постоянные?", "expertise", "work"),
    Question("e_66", "Какие проблемы вы уже помогли решить людям?", "expertise", "work"),
    Question("e_67", "Какие проблемы у вашей ЦА? И какие вы планируете решать?", "expertise", "work"),
    Question("e_68", "Чему вы могли бы научить людей?", "expertise", "work"),

    # ── 2.10 Вдохновение и будущее ──
    Question("e_69", "Ради чего в вашей сфере вы бы с лёгкостью вставали в 5 утра каждый день?", "expertise", "inspiration"),
    Question("e_70", "Есть ли у вас хобби?", "expertise", "inspiration"),
    Question("e_71", "Как часто вы обучаетесь и повышаете квалификацию?", "expertise", "inspiration"),
    Question("e_72", "Опишите вашу деятельность, развитие вашей личности эксперта через 10 лет.", "expertise", "inspiration"),
    Question("e_73", "Как вы можете помочь этому миру (массе людей)?", "expertise", "inspiration"),
    Question("e_74", "Есть ли у вас цель за гранью вашей жизни?", "expertise", "inspiration"),
    Question("e_75", "Какие действия вы можете совершить для привлечения клиентов?", "expertise", "inspiration"),
    Question("e_76", "Чего от вас ждут клиенты сейчас?", "expertise", "inspiration"),
    Question("e_77", "Где вы черпаете вдохновение для работы?", "expertise", "inspiration"),
    Question("e_78", "За что люди вам охотно платят деньги? (за какие результаты?)", "expertise", "inspiration"),

    # ── 2.11 Конфликты и кейсы ──
    Question("e_79", "Как вы относитесь к ошибкам в работе?", "expertise", "cases"),
    Question("e_80", "Какой непредвиденный случай произошёл, и как вам удалось с ним справиться?", "expertise", "cases"),
    Question("e_81", "Часто ли у вас бывают конфликтные ситуации на работе?", "expertise", "cases"),
    Question("e_82", "Как вы решаете конфликты на работе?", "expertise", "cases"),
    Question("e_83", "Что вашим клиентам нравится в вас?", "expertise", "cases"),
    Question("e_84", "Что вашим клиентам не нравится в вас?", "expertise", "cases"),

    # ── 2.12 Убеждения и бренд ──
    Question("e_85", "Напишите 3 убеждения в вашей работе, которые вы никогда не измените.", "expertise", "brand"),
    Question("e_86", "Кем вы мечтали стать в детстве?", "expertise", "brand"),
    Question("e_87", "Ваша деятельность сейчас отражает детскую мечту?", "expertise", "brand"),
    Question("e_88", "Вы работаете по вашему образованию или нет? Почему?", "expertise", "brand"),
    Question("e_89", "Есть ли у вас подарки для ваших клиентов или особые условия?", "expertise", "brand"),
    Question("e_90", "Готовы ли вы сделать скидку или оказать услугу бесплатно, если клиент вам очень симпатизирует?", "expertise", "brand"),
    Question("e_91", "Есть ли у вас опыт обучения или обмена знаниями с коллегами?", "expertise", "brand"),
    Question("e_92", "Какова ваша философия работы в коллективе? Как вы способствуете командной эффективности?", "expertise", "brand"),
    Question("e_93", "Как вы адаптируетесь к быстро меняющейся природе вашей области экспертизы?", "expertise", "brand"),
    Question("e_94", "Как вы взаимодействуете с сообществом экспертов, и какую роль оно играет в вашей работе?", "expertise", "brand"),
    Question("e_95", "Какие методы вы используете для развития своего лидерского потенциала?", "expertise", "brand"),
    Question("e_96", "Как вы поддерживаете своё эмоциональное благополучие и боретесь с профессиональным стрессом?", "expertise", "brand"),
    Question("e_97", "Взаимодействуете ли вы с клиентами после продажи ваших услуг?", "expertise", "brand"),
    Question("e_98", "Как вы реагируете на отказ клиентов, какие действия предпринимаете?", "expertise", "brand"),
    Question("e_99", "Как вы строите и поддерживаете свою личную брендированность в своей области?", "expertise", "brand"),
    Question("e_100", "Есть ли у вас особый стиль, который узнают ваши конкуренты и ваша ЦА?", "expertise", "brand"),
]

# ══════════════════════════════════════════════════════════════
# БЛОК 3: РАСПАКОВКА ПРОДУКТА (100 вопросов)
# ══════════════════════════════════════════════════════════════

PRODUCT_QUESTIONS: list[Question] = [
    # ── 3.1 Философия продукта ──
    Question("pr_01", "Как вы определяете качество вашего продукта?", "product", "philosophy"),
    Question("pr_02", "Какие основные ценности заложены в вашем продукте?", "product", "philosophy"),
    Question("pr_03", "Какую проблему решает ваш продукт для клиентов?", "product", "philosophy"),
    Question("pr_04", "Что отличает ваш продукт от аналогов на рынке?", "product", "philosophy"),
    Question("pr_05", "Какова философия вашего бренда?", "product", "philosophy"),
    Question("pr_06", "Как вы видите развитие вашего продукта в ближайшие 5 лет?", "product", "philosophy"),
    Question("pr_07", "Какие инновации вы внедряете в свой продукт?", "product", "philosophy"),
    Question("pr_08", "Как вы определяете целевую аудиторию вашего продукта?", "product", "philosophy"),
    Question("pr_09", "Какие эмоции вы хотите вызвать у клиентов с помощью вашего продукта?", "product", "philosophy"),
    Question("pr_10", "Какова миссия вашей компании?", "product", "philosophy"),

    # ── 3.2 История создания ──
    Question("pr_11", "Как возникла идея создания продукта?", "product", "origin"),
    Question("pr_12", "Какие трудности вы встретили на начальном этапе?", "product", "origin"),
    Question("pr_13", "Какой был ваш первый продукт или услуга?", "product", "origin"),
    Question("pr_14", "Как менялся ваш продукт со временем?", "product", "origin"),
    Question("pr_15", "Какой момент стал поворотным для вашего бизнеса?", "product", "origin"),
    Question("pr_16", "Какие ошибки вы допускали при разработке продукта?", "product", "origin"),
    Question("pr_17", "Как вы тестировали свой продукт перед запуском?", "product", "origin"),
    Question("pr_18", "Какой была ваша первая клиентская база?", "product", "origin"),
    Question("pr_19", "Как вы привлекали первых клиентов?", "product", "origin"),
    Question("pr_20", "Какой была ваша первая маркетинговая стратегия?", "product", "origin"),

    # ── 3.3 Производство и процессы ──
    Question("pr_21", "Опишите процесс создания вашего продукта от начала до конца.", "product", "production"),
    Question("pr_22", "Какие материалы или ресурсы вы используете?", "product", "production"),
    Question("pr_23", "Как контролируется качество на каждом этапе?", "product", "production"),
    Question("pr_24", "Какие технологии вы используете в производстве?", "product", "production"),
    Question("pr_25", "Сколько времени занимает создание одного продукта/оказание услуги?", "product", "production"),
    Question("pr_26", "Какие этапы производства являются наиболее критичными?", "product", "production"),
    Question("pr_27", "Как вы оптимизируете производственные процессы?", "product", "production"),
    Question("pr_28", "Какие стандарты качества вы соблюдаете?", "product", "production"),
    Question("pr_29", "Как вы управляете запасами и поставками?", "product", "production"),
    Question("pr_30", "Есть ли у вас эксклюзивные поставщики или партнёры?", "product", "production"),
    Question("pr_31", "Какие экологические стандарты вы соблюдаете?", "product", "production"),
    Question("pr_32", "Как вы обеспечиваете безопасность продукции?", "product", "production"),
    Question("pr_33", "Какие сертификаты или лицензии у вас есть?", "product", "production"),
    Question("pr_34", "Как вы адаптируете производство под сезонные колебания?", "product", "production"),
    Question("pr_35", "Какие планы по масштабированию производства у вас есть?", "product", "production"),

    # ── 3.4 Клиентский опыт ──
    Question("pr_36", "Опишите идеального клиента вашего продукта.", "product", "customer"),
    Question("pr_37", "Как клиент узнаёт о вашем продукте?", "product", "customer"),
    Question("pr_38", "Как проходит процесс покупки?", "product", "customer"),
    Question("pr_39", "Какие методы оплаты вы предлагаете?", "product", "customer"),
    Question("pr_40", "Какие гарантии вы предоставляете?", "product", "customer"),
    Question("pr_41", "Как вы работаете с отзывами клиентов?", "product", "customer"),
    Question("pr_42", "Какие вопросы задают клиенты чаще всего?", "product", "customer"),
    Question("pr_43", "Какие самые частые клиентские сомнения, страхи, стереотипы, возражения?", "product", "customer"),
    Question("pr_44", "Какая основная боль и проблема есть у ваших клиентов, которую решает ваш продукт?", "product", "customer"),
    Question("pr_45", "Что именно в вашем предложении цепляет клиентов больше всего?", "product", "customer"),
    Question("pr_46", "Внедрена ли в вашей компании программа лояльности?", "product", "customer"),
    Question("pr_47", "Можете ли вы хотя бы примерно оценить, сколько денег вы сэкономили для своих клиентов или помогли дополнительно заработать?", "product", "customer"),
    Question("pr_48", "Распишите основные этапы работы с клиентом — от первого обращения до получения денег.", "product", "customer"),
    Question("pr_49", "Расскажите, как вы сопровождаете клиента после покупки.", "product", "customer"),
    Question("pr_50", "Опишите самые удачные акции, которые вы проводили.", "product", "customer"),
    Question("pr_51", "Расскажите про финансовые условия работы.", "product", "customer"),
    Question("pr_52", "Расскажите о неудачных кейсах и проанализируйте, почему так произошло.", "product", "customer"),

    # ── 3.5 Конкуренты и рынок ──
    Question("pr_53", "Как вы собираете обратную связь от клиентов?", "product", "competition"),
    Question("pr_54", "Есть ли в вашем бизнесе понятие «лёгкого входа» или бесплатного первого шага?", "product", "competition"),
    Question("pr_55", "Как вы контролируете качество вашего продукта?", "product", "competition"),
    Question("pr_56", "Как вы работаете с претензиями?", "product", "competition"),
    Question("pr_57", "Сформулируйте 3–5 «непродуктовых» причин, почему выгоднее покупать у вас.", "product", "competition"),
    Question("pr_58", "Какие о компании существуют публикации? (комментарии, интервью, колонки)", "product", "competition"),
    Question("pr_59", "Продаются ли книги, написанные ключевыми людьми вашей компании?", "product", "competition"),
    Question("pr_60", "Количество отзывов на сайте и на сторонних ресурсах?", "product", "competition"),

    # ── 3.6 Экспертность и ноу-хау ──
    Question("pr_61", "Является ли компания членом ассоциаций, гильдий, профессиональных объединений?", "product", "knowhow"),
    Question("pr_62", "Владеет ли компания патентами и авторскими правами?", "product", "knowhow"),
    Question("pr_63", "Организует ли ваша компания значимые профессиональные события?", "product", "knowhow"),
    Question("pr_64", "Покажите и расскажите про ваш офис / место работы.", "product", "knowhow"),
    Question("pr_65", "На каком оборудовании вы работаете?", "product", "knowhow"),
    Question("pr_66", "Опишите основные этапы производственного процесса.", "product", "knowhow"),
    Question("pr_67", "Что делается на каждом этапе?", "product", "knowhow"),
    Question("pr_68", "Результат каждого этапа?", "product", "knowhow"),
    Question("pr_69", "Сколько человек занято на каждом этапе?", "product", "knowhow"),
    Question("pr_70", "Сколько времени длится каждый этап?", "product", "knowhow"),
    Question("pr_71", "В чём преимущества вашей технологии производства перед конкурентами?", "product", "knowhow"),
    Question("pr_72", "Можете ли вы показать свою брендированную сувенирную продукцию?", "product", "knowhow"),
    Question("pr_73", "Есть ли у вас собственные софты и программы?", "product", "knowhow"),
    Question("pr_74", "Есть ли у вас рекомендации подрядчиков или поставщиков?", "product", "knowhow"),
    Question("pr_75", "Какие традиции и правила существуют в вашей компании?", "product", "knowhow"),
    Question("pr_76", "Используете ли вы уникальные материалы?", "product", "knowhow"),
    Question("pr_77", "Работают ли с вами уникальные, единственные в своём роде специалисты?", "product", "knowhow"),

    # ── 3.7 Секреты и детали ──
    Question("pr_78", "Раскройте секреты, ноу-хау и нюансы, которые больше никто не использует.", "product", "secrets"),
    Question("pr_79", "Укажите детали и мелочи, по которым можно судить о безупречном качестве.", "product", "secrets"),
    Question("pr_80", "Какие инструкции предоставляются для сборки или использования продукта?", "product", "secrets"),
    Question("pr_81", "Какие функции продукта наиболее часто привлекают внимание покупателей?", "product", "secrets"),
    Question("pr_82", "Как продукт адаптирован к потребностям различных групп пользователей?", "product", "secrets"),
    Question("pr_83", "Есть ли дополнительные функции, которые неприметны с первого взгляда, но добавляют ценность?", "product", "secrets"),
    Question("pr_84", "Каковы гарантии и как обеспечивается сервисная поддержка?", "product", "secrets"),
    Question("pr_85", "Какие обновления или улучшения продукта планируются?", "product", "secrets"),
    Question("pr_86", "Как продукт взаимодействует с другими устройствами или технологиями?", "product", "secrets"),
    Question("pr_87", "Какие аспекты продукта были изменены на основе обратной связи?", "product", "secrets"),
    Question("pr_88", "Как обеспечивается безопасность пользовательской информации?", "product", "secrets"),

    # ── 3.8 Будущее и развитие ──
    Question("pr_89", "Как продукт учитывает изменения в потребностях пользователей со временем?", "product", "future"),
    Question("pr_90", "Какие дополнительные услуги предоставляются для расширения функционала?", "product", "future"),
    Question("pr_91", "Как продукт реагирует, когда что-то идёт не так?", "product", "future"),
    Question("pr_92", "Как продукт поддерживает многозадачность?", "product", "future"),
    Question("pr_93", "Какова степень гибкости продукта для адаптации к различным условиям?", "product", "future"),
    Question("pr_94", "Какова ваша стратегия по предотвращению потенциальных проблем?", "product", "future"),
    Question("pr_95", "Как продукт отвечает на современные тенденции и требования рынка?", "product", "future"),
    Question("pr_96", "Какие экспертные мнения или рецензии о продукте уже существуют?", "product", "future"),
    Question("pr_97", "Может ли этот продукт создать кто-то другой на основе вашего, под вашим контролем?", "product", "future"),
    Question("pr_98", "Какие культурные или социальные аспекты были учтены при разработке продукта?", "product", "future"),
    Question("pr_99", "Какие психологические аспекты были учтены при проектировании?", "product", "future"),
    Question("pr_100", "Как продукт поддерживает принципы доступности для людей с ограниченными возможностями?", "product", "future"),
]


# ══════════════════════════════════════════════════════════════
# ОБЪЕДИНЁННЫЙ БАНК ВОПРОСОВ
# ══════════════════════════════════════════════════════════════

QUESTION_BANK: list[Question] = PERSONALITY_QUESTIONS + EXPERTISE_QUESTIONS + PRODUCT_QUESTIONS

# All valid block names
BLOCKS = ["personality", "expertise", "product"]

# Subblocks per block (ordered)
SUBBLOCKS: dict[str, list[str]] = {
    "personality": ["hobbies", "values", "family", "lifestyle", "philosophy", "deep"],
    "expertise": ["foundation", "journey", "sources", "tools", "mistakes", "hacks", "market", "mission", "work", "inspiration", "cases", "brand"],
    "product": ["philosophy", "origin", "production", "customer", "competition", "knowhow", "secrets", "future"],
}

# Recommended sessions (groups of subblocks)
SESSIONS: dict[str, list[tuple[str, list[str]]]] = {
    "session_1": [
        ("personality", ["hobbies", "values", "family"]),
    ],
    "session_2": [
        ("personality", ["lifestyle", "philosophy", "deep"]),
        ("expertise", ["foundation"]),
    ],
    "session_3": [
        ("expertise", ["journey", "sources", "tools", "mistakes", "hacks", "market"]),
    ],
    "session_4": [
        ("expertise", ["mission", "work", "inspiration", "cases", "brand"]),
        ("product", ["philosophy", "origin", "production"]),
    ],
    "session_5": [
        ("product", ["customer", "competition", "knowhow", "secrets", "future"]),
    ],
}


def get_questions_by_block(block: str) -> list[Question]:
    """Get all questions for a given block."""
    return [q for q in QUESTION_BANK if q.block == block]


def get_questions_by_subblock(block: str, subblock: str) -> list[Question]:
    """Get questions for a specific subblock."""
    return [q for q in QUESTION_BANK if q.block == block and q.subblock == subblock]


def get_questions_for_session(session_name: str) -> list[Question]:
    """Get all questions for a recommended session."""
    session_config = SESSIONS.get(session_name, [])
    result = []
    for block, subblocks in session_config:
        for sb in subblocks:
            result.extend(get_questions_by_subblock(block, sb))
    return result


def get_next_question(block: str, subblock: str, asked_ids: set[str]) -> Question | None:
    """Get next unanswered question in a subblock."""
    available = [q for q in QUESTION_BANK if q.block == block and q.subblock == subblock and q.id not in asked_ids]
    return available[0] if available else None


def get_question_by_id(q_id: str) -> Question | None:
    """Look up a question by its ID."""
    for q in QUESTION_BANK:
        if q.id == q_id:
            return q
    return None