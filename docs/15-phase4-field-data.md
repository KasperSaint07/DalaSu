# Фаза 4: получение полевой разметки US-Ne2

## Согласованный объём фазы 4 — 03.11.2026

Пользователь выбрал уже готовые NDVI-фазы. Фаза 4 включает сезонный анализ,
анализ по приближённым спутниковым фазам растительности и сравнение RF/XGBoost.
В этом объёме работа выполнена; получение полевых записей не требуется.
Фактические стадии по-прежнему неизвестны. Ниже сохранены методика и материалы
для необязательного будущего расширения по полевым наблюдениям. Указания о
незакрытом анализе фактических стадий относятся к исходной, более строгой цели.


Проверено 2026-11-03. Расчёт по фактическим стадиям реализован, но в проекте
нет подтверждённых интервалов за 2023–2024. NDVI-прокси не заменяют эти данные.

## Где искать файл

1. Проверьте ранее скачанный ZIP с AmeriFlux US-Ne2. Искомое имя имеет вид
   `AMF_US-Ne2_BIF_YYYYMMDD.xlsx`. По [описанию BADM](https://ameriflux.lbl.gov/data/aboutdata/badm-data-product/),
   BADM поставляется вместе с потоковыми/метеорологическими данными. Дата в имени —
   дата публикации метаданных, а не год полевых наблюдений.
2. Если архива нет, откройте [страницу US-Ne2](https://ameriflux.lbl.gov/sites/siteinfo/US-Ne2)
   и раздел BADM либо скачайте актуальный пакет станции через Download Data.
   Если сайт запросит вход, используйте свой аккаунт AmeriFlux.
3. Другой путь — [общая страница BADM](https://ameriflux.lbl.gov/data/badm/),
   ссылка Download AmeriFlux BADM (BIF). Для объединённого файла нужна фильтрация
   `SITE_ID = US-Ne2`. Описание [AA-Flx_BIF](https://ameriflux.lbl.gov/resource/badm-for-sites-with-fluxnet-data-product/)
   относится к метаданным всех станций с продуктом AmeriFlux FLUXNET.
4. Сохраните исходный файл без изменений, например в `data/raw/phenology/`.
   Сохраните URL, дату скачивания, версию и условия использования. Не копируйте
   только выбранные даты без исходного файла.

BIF содержит пять полей: станцию, идентификатор группы, название группы,
переменную и значение. Связанные записи нужно читать вместе по идентификатору
группы. Наличие файла BIF не гарантирует наличия фенологии за нужные годы.
Дополнительные сведения включаются по мере предоставления станцией.

## Какие сведения нужны

Нужны записи именно US-Ne2 за 2023 и 2024: подтверждённая культура, даты посева,
всходов, переходов между вегетативной и репродуктивной фазами, созревания и уборки;
по возможности полевые оценки стадий и неопределённость дат. Ищите группы
фенологических событий и операций выращивания, а также комментарии к ним.
[PHEN_EVENT_TYPE](https://ameriflux.lbl.gov/data/badm/badm-standards/PHEN_EVENT_TYPE)
описывает события, дату, метод и неопределённость; это описание схемы, а не
наблюдения станции. [DM_PLANTING](https://ameriflux.lbl.gov/data/badm/badm-standards/DM_PLANTING)
описывает записи посева.

Даты посева и уборки полезны, но сами по себе не задают репродуктивную стадию.
Точечную оценку стадии нельзя растягивать на недели без подтверждения границ.
Не переносите сроки других станций, региональные календари или записи старых лет.

## Если в BADM нет нужных записей

На [официальной странице станции](https://ameriflux.lbl.gov/sites/siteinfo/US-Ne2)
указаны Andy Suyker (`asuyker1@unl.edu`, PI) и Dan Hatch (`dhatch2@unl.edu`, Data Manager).
Можно отправить следующий запрос самостоятельно. Сообщение из проекта не отправлялось.

**Subject:** US-Ne2 field management and crop phenology records for 2023–2024

Dear Dr. Suyker and Mr. Hatch,

I am working on the DalaSu diploma project comparing FAO-56 Penman–Monteith,
Random Forest, XGBoost and residual-correction hybrid models against daily
evapotranspiration at US-Ne2. Our held-out evaluation period is 2023–2024.

To evaluate errors by actual crop growth stage, could you share, or direct me
to, field management and phenology records for US-Ne2 for these two years?
We are looking for confirmed crop identity, planting, emergence, vegetative
and reproductive stages, maturity and harvest dates, including stage
observations, date uncertainty, and any information establishing crop-free periods.

Partial records would also be valuable; we will leave unsupported dates unknown
and will not treat satellite NDVI phases as observed agronomic stages. Please
let us know the appropriate citation and any conditions for using these records.

Thank you for your help.

[Your name, university and supervisor]

## Подключение проверенных записей

После проверки исходника зарегистрируйте его в `data/metadata/phenology/sources.json`
с уникальным `id` и `kind: field_record`. В `observed_intervals.csv` укажите
`start_date,end_date,crop,stage,source_id,evidence_locator,status`.
Даты включительны; пересечения запрещены. `status` должен быть `observed`, а
локатор — ссылаться на конкретный файл/версию и запись, таблицу или страницу.
Разрешённые стадии: emergence, vegetative, reproductive, maturation, off_season.
Неизвестные интервалы оставьте вне CSV — они автоматически останутся unknown.

```bash
PYTHONPATH=src python -m ml.data.build_phenology
PYTHONPATH=src python -m ml.evaluation.phase4 --require-complete-stages
```

Фаза 4 проверяет совпадение ежедневной разметки с исходными интервалами и
сравнивает все семь моделей на одинаковых датах каждой стадии. Неполные данные
дают полезный частичный отчёт; строгая команда возвращает код 2 при неизвестных
стадиях. Код 0 означает полное покрытие тестовых дат, а не достаточный размер
каждой стадии или доказанную значимость. Все ограничения видны в
`reports/phase4_readiness.json` и `reports/phase4_summary.md`.

## Результат повторного поиска

Проверены официальная страница станции, описание BADM и стандарты фенологических
событий, поисковые запросы US-Ne2 с 2023/2024, planting, emergence, harvest и BIF.
Поиск не дал проверяемых интервалов стадий за оба тестовых года. Прямое чтение
части страниц AmeriFlux вернуло HTTP 403; индексированные официальные описания
были доступны. Архив CSP UNL через веб-инструмент недоступен. Это ограничение
получения данных, а не доказательство отсутствия записей у команды станции.

Найденные статьи с историческими данными не использованы для заполнения тестовых
лет. Автоматическое скачивание от имени пользователя и обращения к команде
станции не выполнялись. Все полевые интервалы в production CSV остаются пустыми;
синтетические интервалы существуют только в изолированных автоматических тестах.
