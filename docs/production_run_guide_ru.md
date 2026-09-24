# MANIA Dataset v1: чистый производственный запуск

## 1. Назначение и границы проверки

Руководство описывает установку из чистого Git-клона, автономную установку,
организацию внешних MD-входов, обработку отдельной траектории, внешнюю подготовку
PBC, физическое время, белковые и специализированные контакты, канонизацию, QC,
привязку ручного рецензирования, агрегацию реплик, публикацию Dataset, валидацию
и сохранение доказательств воспроизводимости.

**VERIFIED IN STAGE 34.D:** D.1 — чистая установка; D.2a — wheelhouse;
D.2 — новая обработка трёх реальных NAMD-реплик; R1 — опубликованный в пакете
источник определений контактов; D.2c — чистое повторение публикации после R1.
Принятый Composite D.2 объединяет новую науку D.2 и исправленную публикацию
D.2c. В D.2c исходные MD повторно не рассчитывались: использованы неизменные
результаты чистого D.2. Первоначальные отчёты сохраняют прежние отказы;
последующее принятие учитывает исправление R1 и допустимые различия текущего
происхождения данных. Исторические отчёты не следует переписывать.

Проверенный исходный коммит после R1:
`12c41af718d173f7eb9f073f8cf19b02e5e125dc`, версия MANIA `0.1.0`.
Это руководство не означает, что уже выполнены все производственные траектории
или опубликован Dataset v1.0.

**TO BE VERIFIED IN STAGE 34.E:** конкретная кластерная среда, выделение
ресурсов, планировщик и отправка заданий. Команд планировщика здесь нет.
Stage 34.E должен проверить реальную процедуру запуска на выбранном кластере.

Порядок производства фиксирован:

```text
27–30: наука каждой реплики
→ 32: QC и окончательные решения
→ QC-derived manifest для Stage 31
→ 31: агрегация
→ 33: публикация и полная валидация
```

## 2. Требования и смысл отметок команд

| Параметр | Объявленная поддержка / фактическая проверка |
| --- | --- |
| Python | В `pyproject.toml`: `>=3.11`; в чистом Stage 34.D: `3.12.3` |
| Платформа | Проверена Linux x86_64, WSL2, glibc 2.39; WSL2 не является требованием |
| MANIA | Проверена `mania-wania 0.1.0`; одинаковая версия пакета не заменяет Git SHA |
| MD-стек | Опциональный extra `md`; проверена MDAnalysis `2.10.0` |
| Установка | setuptools / PEP 517, обычный wheel, без editable-установки |

Git, Bash и Python с модулем `venv` нужны для приведённых команд. Доступ к сети
нужен при подготовке wheelhouse; после его проверки установка возможна без сети.
Другая платформа, версия Python или набор зависимостей требуют отдельной проверки.
Требования пакета не являются lockfile: сохраняйте фактически выбранные версии.

`EXECUTED_EQUIVALENT` означает выполненную эквивалентную команду с заменёнными
путями; `STATIC_SAFE` — проверенный синтаксис/интерфейс, без заявления о новом
полном MD-запуске; `STAGE34E_PENDING` — ещё не проверенную кластерную операцию.
Общая отметка VERIFIED не превращает параметризованный пример в доказательство
обработки ваших входов. Аудит D.3 связывает каждый shell-вызов с доказательством.

## 3. Чистый клон и каталоги

Замените значения `/path/to/...` своими абсолютными путями. `REPO_URL` — адрес
доступного Git-репозитория или путь к его принятому источнику. `REPO`, `BUILD_ENV`
и `PROD_ENV` должны быть новыми каталогами; для нового запуска используйте новый
`RUN_ROOT`. Wheelhouse должен содержать одну выбранную сборку MANIA.
Переменные ниже используются во всех следующих разделах в одной Bash-сессии.
Присваивания и организация каталогов — **STATIC_SAFE**.

<!-- command-block: locations -->
```bash
REPO_URL='/path/to/approved/source-repository'
SOURCE_REF='12c41af718d173f7eb9f073f8cf19b02e5e125dc'
REPO='/path/to/fresh/MANIA_WANIA'
BUILD_ENV='/path/to/build-env'
PROD_ENV='/path/to/production-env'
WHEELHOUSE='/path/to/wheelhouse'
RUN_ROOT='/path/to/run_root'
mkdir -p "$RUN_ROOT/inputs" "$RUN_ROOT/controls" "$RUN_ROOT/reviews" "$RUN_ROOT/outputs" "$RUN_ROOT/evidence" "$WHEELHOUSE"
```

Клонируйте Git-репозиторий; не копируйте существующую рабочую директорию.
`--no-local` использован в D.1/D.2 для независимого клона локального источника.
Для сетевого URL Git применяет обычный сетевой transport.
Команды клонирования/checkout/проверки — **EXECUTED_EQUIVALENT**;
сохранение SHA в файл — **STATIC_SAFE**.

<!-- command-block: clone -->
```bash
git clone --no-local "$REPO_URL" "$REPO"
git -C "$REPO" checkout --detach "$SOURCE_REF"
git -C "$REPO" rev-parse HEAD
git -C "$REPO" status --short
git -C "$REPO" rev-parse HEAD > "$RUN_ROOT/evidence/source_head.txt"
```

Вывод status должен быть пустым, SHA — совпадать с выбранным принятым коммитом.
Вместо указанного SHA можно выбрать другой принятый коммит/тег, но всегда
сохраняйте разрешённый полный SHA и проверяйте наличие R1. Подвижное имя ветки
и строка `0.1.0` не определяют точную реализацию. Производственная среда не должна
зависеть от разработческой `.venv`. В wheel без Git-метаданных программный
`commit_sha` может быть `null`; внешний `source_head.txt` сохраняет эту связь.

Рекомендуемая структура отделяет код, внешние данные и результаты:

```text
fresh/MANIA_WANIA/                 Git-клон
production-env/                   установленный пакет и зависимости
wheelhouse/                       проверенный комплект wheel
run_root/
  inputs/raw/shared/              общая топология и исходные определения
  inputs/raw/<trajectory_id>/     траектория, config, log, XSC
  controls/                      полномочия, mapping, manifests
  reviews/                       решения и основания рецензентов
  outputs/<trajectory_id>/        подготовленные координаты и наука
  outputs/qc_initial/             первое решение QC
  outputs/qc/                     окончательный QC
  outputs/aggregation/            Stage 31
  outputs/publication/            только поверхность Stage 33
  evidence/                      команды, версии, проверки, хеши
```

Это схема каталогов, а не готовый manifest. Raw MD и большие результаты не
помещают в Git. Для переносимых downstream-controls пути задаются относительно
родительского каталога соответствующего manifest, без абсолютных путей,
`..` и подстановок переменных. Удобно размещать QC/release-control в `RUN_ROOT`,
чтобы `controls/`, `reviews/` и `outputs/` были доступны ниже одного корня.
Правила preprocessing и Stage 31 отличаются; следуйте их собственным readers.

## 4. Установка с доступом к сети

**VERIFIED IN STAGE 34.D.** Сборка wheel проверена в D.1/D.2a, разрешение `[md]`
— в D.2a. Следующие команды повторяют этот механизм. Онлайн-установка wheel
с `[md]` объединяет эти проверенные операции и имеет отметку **STATIC_SAFE**;
полностью автономная установка `[md]` непосредственно проверена в D.2a/D.2c.

<!-- command-block: online -->
```bash
python3.12 -m venv "$BUILD_ENV"
"$BUILD_ENV/bin/python" -m pip install --no-cache-dir --upgrade pip setuptools wheel
"$BUILD_ENV/bin/python" -m pip wheel --no-cache-dir --no-deps --wheel-dir "$WHEELHOUSE" "$REPO"
python3.12 -m venv "$PROD_ENV"
"$PROD_ENV/bin/python" -m pip install --no-cache-dir --report "$RUN_ROOT/evidence/online_pip_report.json" "$WHEELHOUSE/mania_wania-0.1.0-py3-none-any.whl[md]"
"$PROD_ENV/bin/python" -m pip check
```

`python3.12` выбран для воспроизведения проверенной среды. При другом допустимом
Python замените его последовательно и проверьте среду заново. Сборка использует
метаданные клона; `[md]` устанавливает объявленный MDAnalysis и его зависимости.
Extra `dev` производственному пользователю не нужен. Имя wheel выше относится
к проверенной версии `0.1.0`; для другой принятой версии используйте её реальное
имя и сохраните хеш/связь с исходным SHA.

## 5. Автономная установка через wheelhouse

На машине с сетью выполните клонирование и сборку из предыдущих разделов,
затем разрешите зависимости wheel с `[md]`. Это **EXECUTED_EQUIVALENT** D.2a.
Устанавливать онлайн в `PROD_ENV` для этой ветки не требуется.

<!-- command-block: resolve-wheels -->
```bash
"$BUILD_ENV/bin/python" -m pip wheel --wheel-dir "$WHEELHOUSE" --index-url https://pypi.org/simple/ "$WHEELHOUSE/mania_wania-0.1.0-py3-none-any.whl[md]"
```

Не переносите старый MANIA wheel только потому, что его версия тоже `0.1.0`.
В D.2c использована новая сборка после R1 и проверенные сторонние wheels D.2a;
старый MANIA wheel был исключён. Проверьте wheel METADATA, объявленный extra
`md`, версии и происхождение файлов; сохраните отчёт разрешения зависимостей.
Wheelhouse зависит от Python, ABI, ОС и архитектуры, пока переносимость отдельно
не доказана. Сам MANIA wheel `py3-none-any` не делает весь MD-стек универсальным.

Следующий компактный SHA256-реестр — **STATIC_SAFE**: в D.2a использовался более
полный JSON manifest с размерами, версиями, URL и хешами. Реестр строится на
доверенной стороне после комплектования, переносится вместе с wheels и
проверяется перед установкой; не создавайте новый «эталон» уже после переноса.

<!-- command-block: wheel-hashes -->
```bash
(cd "$WHEELHOUSE" && sha256sum -- *.whl > SHA256SUMS)
(cd "$WHEELHOUSE" && sha256sum --check SHA256SUMS)
```

На целевой машине заново задайте переменные путей; `WHEELHOUSE` теперь указывает
на перенесённый комплект. Создайте новый `PROD_ENV` командой создания среды из
раздела 4, если он ещё не создан. Изолированная установка —
**EXECUTED_EQUIVALENT** D.2a/D.2; сеть и сборка из sdist не используются:

<!-- command-block: offline -->
```bash
"$PROD_ENV/bin/python" -I -m pip --isolated --disable-pip-version-check --no-cache-dir install --no-index --find-links "$WHEELHOUSE" --only-binary=:all: --report "$RUN_ROOT/evidence/offline_pip_report.json" "$WHEELHOUSE/mania_wania-0.1.0-py3-none-any.whl[md]"
"$PROD_ENV/bin/python" -I -m pip check
```

Ожидаемый результат проверки: `No broken requirements found.` Отчёт установки
должен ссылаться на локальные файлы проверенного комплекта. Отсутствующий или
несовместимый wheel означает остановку; отключать `--only-binary` или подменять
зависимости непроверенными файлами нельзя. Повторяемость выбранного окружения
подтверждается сохранёнными wheels/хешами, а не повторным сетевым разрешением.

## 6. Изоляция исполнения и ресурсы пакета

Подготовка сессии — **STATIC_SAFE**. Остальные проверки версий/импортов имеют
выполненные эквиваленты в D.1/D.2a/D.2c. Работайте из каталога вне исходного кода.

<!-- command-block: runtime -->
```bash
unset PYTHONPATH PYTHONHOME
export PYTHONNOUSERSITE=1
source "$PROD_ENV/bin/activate"
cd "$RUN_ROOT"
which python
which mania
python -c "import mania; print(mania.__file__)"
python -c "import MDAnalysis; print(MDAnalysis.__file__)"
mania --version
python -m mania --version
python -m pip check
python -m pip freeze > "$RUN_ROOT/evidence/pip_freeze.txt"
mania validate-config "$REPO/configs/mania.example.yaml"
```

Оба executable и оба импорта должны относиться к `PROD_ENV`, а не к исходному
`src`, пользовательскому site-packages или чужой среде. Обе команды версии
должны вывести `mania-wania 0.1.0`. Проверка example config должна сообщить
`Config is valid`; она проверяет конфигурацию, но не существование raw MD,
неправильно заданное научное время или готовность реального Dataset-run.

Проверка доступности packaged-ресурсов ниже — **STATIC_SAFE**, дополнительно
исполнена при проверке D.3. Загрузчик R1 сам проверяет хеш authority при её
использовании; простая проверка наличия не заменяет этот контроль.

<!-- command-block: resources -->
```bash
python -c "from importlib.resources import files; p=files('mania'); assert p.joinpath('data/canonical/slc34a2_o95436_reference.json').is_file(); assert p.joinpath('data/publication/contact_definition_authority_v1.json').is_file(); print('Packaged authorities available')"
```

## 7. Реальные входы и управляющие документы

Для проверенного класса NAMD-входов нужны общие PSF и полный использованный
набор исходных toppar/определений (`.rtf`, `.prm`, `.str`, `.crd` по фактическому
комплекту). Для каждой реплики сохраняются DCD, production config, production
log и XSC. Сохраняйте оригинальную связь имён, хеши и основания соответствия
топологии/координат: DCD не содержит идентичностей атомов. Config/log читаются
как источники полномочий, не исполняются как NAMD/Tcl-команды.

Система NAMD из D.2 — пример конкретного WT/2SS/PMm-контракта, не универсальная
метка условия или схема времени. Источники могут иметь различный engine,
variant, disulfide state и production interval. Нельзя переименовывать научное
условие по имени каталога или по служебному routing-полю `condition`.

Для GROMACS документация репозитория использует topology `.tpr` и trajectory
`.xtc`; в политике внешнего хранения также перечислены `.gro`, `.trr`, `.edr`
и журналы. Сохраняйте исходные определения системы, реальные параметры
и журнал производства вместе с координатами.
Поддержку конкретной комбинации reader/топологии проверяют отдельно.
В D.2 выполнен NAMD-chain: полный чистый GROMACS-production этим checkpoint
не проверен. Здесь нет команд запуска GROMACS или непроверенного полного
GROMACS-сценария. См. [политику входов](data_sources.md) и
[диагностику PBC](stage34_pbc_diagnostic.md).

| Управляющий документ | Уровень и обязательная привязка |
| --- | --- |
| Atom-type → element для NAMD | Общий только для точного PSF/toppar; проверяются хеши, все использованные типы и принятые ручные определения |
| Физическое время | Для каждой траектории: её DCD/config/log, начало, шаги записи и исходная временная ось |
| Canonical mapping | Можно разделять при доказанно одинаковой топологии; явная привязка к источнику и каждой полной replica key обязательна |
| System metadata и biological annotations | Полная система: engine/variant/condition/disulfides, все требуемые канонические позиции и биологические признаки |
| PBC protocol approval | Общий принятый протокол плюс отдельные диагностика и проверка сохранённых координат каждой траектории |
| Partner classification | Принятые определения конкретной системы; локальный каталог и atom-index evidence для каждой топологии/траектории |
| QC/reviews | Каждая реплика, метод, интервал, результаты наблюдений, идентичности файлов и автор решения |
| Partner correspondence | Отдельные утверждённые межрепличные соответствия для конкретной группы/окна |

Нельзя угадывать элементы PSF по именам/массе или переносить список липидов и
гликанов с другой системы. Пустые/неразрешённые полномочия не превращаются в
отрицательные наблюдения. Форматы:
[NAMD authority](stage34b_namd_authority.md),
[Dataset identity](dataset_identity_contract.md),
[partner metadata](specialized_contact_window_contract.md),
[annotations](biological_annotation_contract.md).

## 8. Физическое время: requested и effective

Для NAMD scientific production time задаётся принятой системно-специфичной
config/log authority и точной последовательностью записи координат.
Raw DCD reader `dt` сохраняется как наблюдение, но автоматически не становится
временной authority публикации. NAMD-loader принимает явные element/time
controls; адаптер времени устанавливается до геометрических преобразований.

Stage 27 использует фактические `timestep.time` в ps и сохраняет отдельно:

- requested: production start/end, stride и полный контракт окон;
- effective: разрешённые source frame indexes, фактические времена, пропуски,
  покрытие и членство кадров в каждом окне.

Результат — `temporal_execution.json`; requested-контракт остаётся в provenance.
Не подменяйте requested интервал фактическими границами, чтобы скрыть пропуски.
Stage 27 может вернуть partial; Stage 32 отдельно применяет политику 95%.
Для Dataset-запуска старые frame start/stop/stride/max_frames должны оставаться
в значениях по умолчанию. Обычные физические окна полуоткрыты; полное окно,
точно заканчивающееся на production end, включает правый конец. Частичное
последнее окно не добавляют произвольно.

Пять кадров и времена 0.1–0.5 ns в D.2 — исключительно короткий технический
пилот. Они не задают production timing всех 33 траекторий. Подробности:
[Stage 27 execution](physical_time_execution_contract.md) и
[window contract](physical_time_window_contract.md).

## 9. Внешняя подготовка PBC

Принятый протокол: **unwrap bonded fragments → center on protein → wrap complete
bonded fragments**. В проверенном варианте белок центрируется геометрически
с `wrap=False`; затем целые fragments оборачиваются с `center="cog"`.
**MANIA production internal MIC = false.** Это внешняя подготовка координат,
а не включение minimum-image correction внутри расчёта контактов.

Для каждой траектории сохраните параметры преобразований, исходную и новую
идентичность координат, порядок атомов, box/time, диагностику связей, белка,
дисульфидов и гликановых якорей/ветвей, если они присутствуют. Проверяйте и
сохранённую/reopened траекторию. В D.2 использован отдельный prepared XTC;
raw DCD сохранён неизменным. Допуск 0.001 Å относился к проверке согласованности
представлений пилота, а не к расширению научных cutoffs; пограничные flips
учтены отдельно. Этот допуск нельзя выдавать за универсальную QC-политику.

Одобрение протокола не означает, что конкретная траектория уже прошла аудит.
Автоматический `pbc_audit.json` MANIA является observation-only и сам не
доказывает успешную внешнюю подготовку. В контракте R1 историческое поле
`historical_scientific_pbc_status="unresolved"` сохраняется вместе с явными
текущими approval/diagnostics; его не переписывают ради косметического PASS.

## 10. Одна траектория: интерфейсы и порядок

Порядок: проверка input authority → подготовка/аудит PBC → выбор по физическому
времени → protein contacts/windows → specialized contacts, если применимо
→ canonicalization → техническая валидация → QC evidence.

Поддерживаемый CLI preprocessing — `mania preprocessing run-graph-export`.
Он требует подготовленного manifest с Dataset binding, временным контрактом,
`canonical_residue_mapping_path`, `biological_annotation_metadata_path`
и, при необходимости, `molecular_partner_metadata_path` в соответствующих
conditions. Dataset binding задаётся `dataset_spec` либо явным `dataset_ref`
и `dataset_parameter_table_path` по правилам Stage 26.
Manifest с placeholder-входами не является production manifest.

**STATIC_SAFE:** следующий шаблон проверен по CLI и тестам; это не самостоятельное
повторение NAMD D.2. Он применим, когда обычный runtime уже получает правильные
элементы и время из подготовленных входов. Идентификатор задаётся явно, не
выводится из имени файла. Флаги сохранения intermediates соответствуют D.2;
`--skip-rg` означает, что Rg не вычисляется.

<!-- command-block: preprocessing -->
```bash
TRAJECTORY_ID='replace-with-authoritative-trajectory-id'
mania preprocessing run-graph-export --manifest "$RUN_ROOT/controls/$TRAJECTORY_ID/preprocessing_manifest.json" --output "$RUN_ROOT/outputs/$TRAJECTORY_ID/preprocessing" --run-name "$TRAJECTORY_ID" --contact-selection protein --skip-rg --export-analysis-inputs --export-contact-edges --export-contacts-perframe --artifact-checksum-mode sha256
```

**Ограничение NAMD.** Публичной CLI-опции для element/time authority нет.
Действующий API:
`mania.preprocessing.trajectory_loader.load_single_condition_runtime(runtime_input,
namd_authority=NAMDControlPaths(elements_path, time_path))`, где `NAMDControlPaths`
импортируется из `mania.preprocessing.namd_runtime`. Это явный loader исходного
PSF/DCD; control исходного DCD нельзя механически назначить prepared XTC.

В реальном D.2 внешняя оркестрация проверяла controls, готовила XTC, явно
прикрепляла элементы и точное время, затем вызывала production CLI внутри
процесса с проверенным prepared-loader. Печатный argv этого CLI без loader
не эквивалентен выполненному запуску. Специализированная стадия D.2 использовала
production API через тот же evidence-harness; канонизация и проверки потребляли
полученные source tables и явный mapping.

Ниже **EXECUTED_EQUIVALENT**, только исторический образец фактически успешных
вызовов D.2; не запускайте их поверх замороженных доказательств. `D2_ROOT`
обозначает отдельный корень принятого evidence-пакета с `repo/`, `inputs_real/`,
`outputs/`, `evidence/`. Скрипт `run_clean.py` находится в архиве D.2, не в
устанавливаемом пакете; содержит проверки конкретной системы и пяти кадров.
Для новой системы нужен отдельно проверенный orchestration adapter с её
входами, полной временной областью и текущими путями. Простая замена `D2_ROOT`
в команде не адаптирует внутренние ограничения скрипта.

<!-- command-block: historical-orchestration -->
```bash
D2_ROOT='/path/to/accepted-d2-evidence-root'
python -I "$D2_ROOT/evidence/run_clean.py" preflight
python -I "$D2_ROOT/evidence/run_clean.py" resume_prepared 1
python -I "$D2_ROOT/evidence/run_clean.py" replica 2
python -I "$D2_ROOT/evidence/run_clean.py" replica 3
```

`resume_prepared 1` был успешным продолжением только нового, уже проверенного
prepared-файла после отказа до расчёта контактов. Это не команда запуска первой
реплики с нуля. Универсального автоматического raw-NAMD → release launcher
данный checkpoint не предоставляет. Готовность научного ядра и это ограничение
оркестрации следует учитывать отдельно. Старый `mania run` остаётся заглушкой;
он не выполняет Dataset-chain. Проверка конкретного полного запуска относится
к дальнейшей подготовке и Stage 34.E, а не к вымышленной команде из этого текста.

## 11. Белковые и специализированные научные правила

Для protein windows denominator occupancy — только resolved frames данного
окна. Missing expected sample не является отрицательным контактом и не входит
в denominator, но разрывает непрерывность эпизода. `gap_tolerance = 0`.
Намеренно запрошенный stride не разрывает эпизод: непрерывность определяется
соседними requested sample indexes. Длительность берётся по фактическому времени
первого/последнего положительного кадра; lifetime одного кадра — `0 ns`.
`edge_weight = occupancy`. Типы protein edges сохраняются раздельно согласно
`edge_semantics.json`; не объединяйте их в одно описание контакта.

| Слой | Геометрия и граница |
| --- | --- |
| protein-lipid | Минимальное декартово расстояние между тяжёлыми атомами, `<= 6.0 Å` |
| protein-glycan | Минимальное декартово расстояние между тяжёлыми атомами, `<= 4.5 Å` |

Specialized occupancy/episodes используют те же правила resolved frames и
эпизодов. `distance_mean_A` и `distance_min_A` вычисляются только по положительным
контактным кадрам, а не по всем кадрам окна. Для гликана сохраняется явное
исключение ковалентного якоря carrier/first sugar из стандартной noncovalent
сводки: исключается carrier ↔ whole-glycan observation, а не удаляются атомы
первого сахара из поиска минимума. Исходное положительное наблюдение
и основание исключения не стираются.
**Специализированного `edge_weight` нет.** Эти правила не вводят новых формул:
см. [episodes](contact_episode_lifetime_contract.md),
[protein windows](protein_edge_window_aggregation_contract.md),
[specialized windows](specialized_contact_window_contract.md).

## 12. Канонические идентичности

Цель Dataset — UniProt **O95436 / O95436-1, 690 aa**, packaged reference
`uniprotkb:O95436-1:sequence-v3`. Mapping source → canonical задаётся явно
по engine/chain/resid/resname, с проверкой реальной топологии и полной replica key
`(dataset_id, system_id, trajectory_id, replica_id)`. Равенство числового source
`resid` каноническому номеру не доказывает mapping.

Stage 30 сохраняет исходные идентичности и научные значения, добавляя канонические
таблицы. Например, source MET в T330M может явно соответствовать canonical
`330 THR`; вариант остаётся в system metadata. Нужны полный mapping и полные
system annotations, а не только позиции, встречающиеся в sparse edges.
См. [mapping](canonical_residue_mapping_contract.md) и
[canonical tables](canonical_window_table_contract.md).

## 13. Техническая валидация и внешние input bindings

**STATIC_SAFE:** CLI-оболочка ниже проверена; полная проверка требует всех
внешних входов из `artifact_inventory.json`. Простое отсутствие mappings может
дать `partial` и код 0, что не является полной приёмкой.

<!-- command-block: preprocessing-validation -->
```bash
mania artifacts validate "$RUN_ROOT/outputs/$TRAJECTORY_ID/preprocessing" --scope preprocessing
```

Для полной проверки повторяйте CLI-параметр `--input-artifact-path ARTIFACT_ID=PATH`
для **каждого** input-артефакта с его реальным ID и путём; не угадывайте ID.
Эквивалентный API `mania.validation.unified.validate_run_artifacts` принимает
`input_artifact_paths` как явное отображение ID → Path. Успех production-gate:
`status=passed`, `complete=true`, без ошибок и непроверенных обязательных ролей.
Прочитайте JSON-отчёт, а не только process exit code. Валидация технических
артефактов не заменяет индивидуальный PBC/QC-аудит.

## 14. Stage 32: QC и ручное рецензирование

После науки каждой реплики сформируйте реальные hard/review evidence и QC
manifest. Не подставляйте synthetic fixture в production. Проверяются читаемость
и порядок атомов, mapping, PBC, требуемые metadata/artifacts и полнота sampling.
При `<95%` ожидаемых production samples действует hard exclusion Stage 32;
знаменатель берётся из авторитетного запрошенного sampling-контракта.

**STATIC_SAFE:** публичный CLI соответствует production API, выполненному в
D.2; сами manifests для вашей системы должны быть подготовлены и проверены.
Первый проход и окончательный проход имеют разные output roots.

<!-- command-block: qc-initial -->
```bash
mania dataset qc --manifest "$RUN_ROOT/dataset_qc_manifest_initial.json" --output "$RUN_ROOT/outputs/qc_initial" --artifact-checksum-mode sha256
```

Изучите findings. Hard FAIL даёт excluded; hard PASS + review PASS может дать
available автоматически. Обязательный неразрешённый REVIEW означает
`pending_review`, `production_ready=false`; при этом завершённый QC может
вернуть exit 0, но QC-derived manifest не создаётся.

При необходимом ручном разрешении сохраните reviewer, reason, note,
`decision_evidence_ids` и решение available/excluded в `manual_resolution`
окончательного QC manifest. Reason и evidence IDs должны соответствовать
реальному REVIEW finding. Hard FAIL или чистый PASS нельзя переопределить
произвольным ручным решением. При automatic PASS окончательный manifest может
содержать те же controls без ручного разрешения.

<!-- command-block: qc-final -->
```bash
mania dataset qc --manifest "$RUN_ROOT/dataset_qc_manifest_final.json" --output "$RUN_ROOT/outputs/qc" --artifact-checksum-mode sha256
```

Ручная RMSD-оценка — конкретное внешнее заключение, не универсальный RMSD cutoff.
В пилоте рецензирование относилось только к пяти кадрам 0.1–0.5 ns, конкретной
реплике, выборке 690 CA, equal-weight Kabsch и собственному начальному кадру.
Перенос решения на новую репродукцию потребовал проверки той же identity,
области, метода и научного evidence basis; численный допуск сравнения не был
порогом drift. Такой review не разрешает полную production-траекторию.
Принятый пилот дал pass/available для всех трёх реплик; синтетическая проверка
исключения не является фактическим исключением реальной реплики.

Сохраните `dataset_qc_decision_set.json`, summary, findings/evidence и полную
валидацию scope `dataset_qc` с bindings всех controls/reviews. Требуйте
`production_ready=true`. Формат и правила:
[QC workflow](dataset_qc_workflow.md), [hard QC](dataset_hard_qc.md),
[review QC](dataset_review_qc.md).

## 15. Stage 31: агрегация только после окончательного QC

Используйте именно `replica_aggregation_manifest_qc_derived.json`, созданный
окончательным QC. Manifest до QC не определяет production availability.
Группы должны иметь явно заданные expected replicas, одинаковую систему/engine
и совместимые requested physical windows; один `window_id` не доказывает
совместимость. Дождитесь решений по всем кандидатам группы.

**STATIC_SAFE:** проверенный публичный CLI над тем же API, который выполнен D.2.

<!-- command-block: aggregate -->
```bash
mania dataset aggregate-replicas --manifest "$RUN_ROOT/outputs/qc/replica_aggregation_manifest_qc_derived.json" --output "$RUN_ROOT/outputs/aggregation" --artifact-checksum-mode sha256
```

Для protein vector отсутствие sparse edge у **available** реплики даёт ноль
occupancy только в статистическом векторе. **Excluded/unavailable** реплики
не дают ноль и не входят в denominator. Исходные sparse rows не дописывают.
Статистики: mean, median, sample SD (`ddof=1`, знаменатель `n-1`), число available,
supporting и support fraction. Для одной available реплики SD — `null`, не 0.
При отсутствии доступных наблюдений допускается пустая агрегатная таблица.
Выполните полную валидацию scope `replica_aggregation` с bindings всех входов.
См. [aggregation workflow](replica_aggregation_workflow.md) и
[protein vector semantics](replica_protein_edge_aggregation_contract.md).

## 16. Межрепличное соответствие специализированных партнёров

Корректная lipid/glycan science каждой реплики **не устанавливает** соответствие
партнёров между репликами. Совпадение имени липида, local partner ID или порядка
остатков недостаточно. Нужны отдельные утверждённые correspondence records,
покрывающие всех available членов группы. QC проецирует членство таких records
на доступный набор, сохраняя оставшиеся identity/bindings.

Без утверждённого correspondence специализированную aggregate science не
создают. Header-only lipid/glycan aggregate publication допустима и использована
в D.2/D.2c. Она не означает нулевые контакты: per-replica specialized science
сохраняется отдельно. Даже при correspondence Stage 31 агрегирует occupancy
и support, а не distance/lifetime. См.
[specialized aggregation](replica_specialized_aggregation_contract.md).

## 17. R1: построение contact definitions из текущих источников

Publication contact definitions строятся из `edge_semantics.json` для protein,
текущего `run_provenance.json`/конфигурации, текущих PBC approval/diagnostics
и partner catalogs. Specialized authority хранится в репозитории:

`src/mania/data/publication/contact_definition_authority_v1.json`

Schema — `mania.publication_contact_definition_authority.v1`, contract version
`1`, SHA256 — `6beafe903e8ca10fc8b9d749108043c3d2c366aed0d516cc4a8041054a89c597`.
Этот ресурс включён в wheel. Старые `publication_inputs.json` не нужны как seed.

API модуля `mania.dataset_release_contact_definition_authority`:

1. `materialize_contact_definition_authority(workspace, path)` сохраняет точные
   packaged bytes по явному переносимому пути.
2. `build_dataset_release_contact_definitions(...)` принимает `workspace`, полную
   `replica_key`, `edge_semantics_path`, `run_provenance_path`,
   `pbc_correction_status` и, для specialized, `specialized_authority_path` плюс
   `partner_catalog_path`.
3. `.to_dict()` каждой возвращённой модели даёт nested definition для нового
   publication input; `.to_table()` — строгую проекцию Stage 33.

PBC binding включает `internal_mic=false`, явное
`external_protocol_approved=true`, сохранённое историческое поле и реальные
пути `protocol_authority` / `trajectory_preparation_and_diagnostics`.
Конструктор проверяет bindings и определения, но сам не выполняет PBC-аудит.
Обе specialized-привязки можно опустить для построения только protein definitions.

Новый `publication_inputs.json` всё равно является входом Stage 33: его
**конструируют заново**, а не копируют исторический файл. Сохраняются отдельные
interaction types и текущие runtime cutoff/selection/resolved count.
Software records берутся из текущих явно связанных run provenance; metrics
содержат только значения с утверждёнными источниками. Публичной отдельной
CLI-команды конструктора пока нет; используется API, как в D.2c.
Полный пример bindings и строгие требования:
[R1 authority](dataset_release_contact_definition_authority.md).

## 18. Stage 33: публикация, F1, F2 и полный release

До публикации заморозьте авторитетные результаты и подготовьте export manifest:
Stage 32 и Stage 31 provenance/inventory с **полными** input bindings; решения
QC и summary; QC-derived manifest и точный manifest использованной агрегации;
aggregate outputs; canonical science bindings всех публикуемых семейств;
temporal evidence; полные system annotations; новый publication input;
явные replica/system selections. Отсутствующую sparse family не подменяют
несуществующим файлом: предусмотрите корректный header-only artifact/binding.

**STATIC_SAFE:** публичная CLI-оболочка production API, использованного в D.2c:

<!-- command-block: publish -->
```bash
mania dataset publish --manifest "$RUN_ROOT/dataset_release_export_manifest.json" --output "$RUN_ROOT/outputs/publication" --artifact-checksum-mode sha256
mania artifacts validate "$RUN_ROOT/outputs/publication" --scope dataset_release --input-artifact-path "input:dataset_release_export_manifest=$RUN_ROOT/dataset_release_export_manifest.json"
```

Последовательность контроля: upstream lineage → **F1** → **F2** → cross-table
validation → complete release validation. Эти проверки встроены в assembly
и реконструкцию; отдельных вымышленных CLI-флагов F1/F2 нет. API доказательств:
`validate_release_canonical_source_authority`, `validate_publication_metric_sources`
в `mania.dataset_release_source_authority`, `validate_dataset_release_tables`
в `mania.dataset_release_validation`, затем unified `validate_run_artifacts`.

F1 защищает полное равенство canonical science реальным источникам Stage 31:
identity, rows, counts, occupancy, episodes/lifetime, distances и прочие поля.
F2 защищает source authority **каждой выведенной** metric, включая значение,
единицы и физическое окно. При пустом `metrics.csv` F2 PASS не доказывает
готовность article metrics. Cross-table проверяет связи и populations;
полная валидация независимо реконструирует ожидаемый release.

Требуйте `status=passed`, `complete=true`; сохраняйте отчёты за пределами
`outputs/publication`, где разрешены только контрактные артефакты. Не заменяйте
неудачный validator ручным редактированием результатов. См.
[release workflow и формы manifests](dataset_release_workflow.md).

## 19. Ожидаемые результаты

Stage 33 создаёт **17 CSV + 3 JSON**. Число научных строк определяется входами,
а не числом строк пилота.

| Категория | Основные результаты |
| --- | --- |
| Канонический белок | `nodes.csv`, 690 canonical positions; полные `residue_annotations.csv` для публикуемых систем |
| Per-replica science | Protein edges и lipid/glycan contacts by window с canonical identity |
| QC | Simulations, quality control, findings, evidence; сохраняются и исключённые кандидаты |
| Aggregates | Protein и при наличии correspondence specialized occupancy/support statistics |
| Контракт измерений | `contact_definitions.csv`, `time_windows.csv` |
| Программная среда | `software_versions.csv` с текущими источниками |
| Метрики | `metrics/metrics.csv`, только авторитетные значения |
| Release | `release/dataset_manifest.json`, `release/provenance.json`, `release/artifact_inventory.json` |

Header-only допустим, если ожидаемая population действительно пуста: sparse
science без положительных контактов, aggregates без соответствующего набора,
specialized aggregates без correspondence, metrics без утверждённых записей.
Это не способ скрыть потерянные непустые источники или неполные обязательные
nodes/annotations/metadata. Сохраняйте также preprocessing source/canonical
tables, catalogs, temporal evidence и upstream QC/aggregation bundles: они
нужны для реконструкции, хотя не все входят в двадцать файлов публикации.
Inventory не включает собственный хеш или циклический хеш provenance.

## 20. Воспроизведение: равная наука и правдивое происхождение

Новый чистый запуск **должен** нести текущие run IDs согласно контракту workflow,
source paths, фактические timestamps и идентичности evidence artifacts.
Не копируйте историческое provenance ради побайтового равенства. У Stage 33
release run ID остаётся контрактным `dataset-release:<dataset_id>:1.0`;
это не отменяет текущих upstream run IDs, путей и времени выполнения.

Урок D.2c: byte-identical science совместима с новыми QC evidence paths,
software source/run bindings, upstream manifest paths, timestamps и связанными
размерами/хешами inventory. R1 дополнительно изменил источник specialized
definition с исторического пояснения на packaged JSON authority. Эти различия
классифицируются явно; научные параметры, единицы и типы нельзя включать в
произвольную «нормализацию».

| Класс сравнения | Как трактовать |
| --- | --- |
| `IDENTICAL_BYTES` | Детерминированные научные артефакты совпали побайтово |
| `SCIENTIFICALLY_EQUAL` | Полные строгие модели совпали; различие представления отдельно объяснено |
| `EXPECTED_PROVENANCE_DIFFERENCE` | Текущие пути, IDs, timestamps и доказанные последствия для inventory |
| `NUMERIC_PLATFORM_DIFFERENCE` | Требует отдельного численного анализа; не автоматическое разрешение любого drift |
| `UNEXPECTED_DIFFERENCE` | Изменение науки/authority либо необъяснённое отличие: остановка и разбор |

Для независимой репродукции сначала завершите и хешируйте новый результат,
затем открывайте baseline только для сравнения. Научное равенство и правдивое
текущее происхождение требуются одновременно. Не перезаписывайте новый release
старым и не изменяйте frozen outputs после сравнения.

## 21. Метрики статьи и сохранение intermediates

Принятый audit: **core Dataset science готова к production; article metric
readiness — PARTIAL**. Legacy `mania analyze` нельзя автоматически считать
источником Stage 27 physical-window metrics: его source identities и временные
окна не получают такую authority от совпадения имени окна. PCA опциональна.
Это не блокирует core trajectory production при выполнении требований
сохранения; не означает разрешения массового запуска до организационной приёмки.

Чтобы не пересчитывать raw MD без необходимости, сохраните:

- canonical edge-by-window tables всех нужных interaction types, включая
  specialized science там, где она применима;
- полный набор canonical nodes, source residues и явный mapping, включая
  изолированные позиции; полные biological annotations;
- Stage 27 requested/effective sampling и window authority, source frame/time
  correspondence, membership и пропуски;
- QC decisions/reviews, group controls и точные aggregation manifests;
- partner catalogs/classification и correspondence authority, если она есть;
- per-frame contact intermediates и полный реестр выбранных кадров, включая
  кадры без контактов, если выбранные будущие анализы требуют этого уровня.

Одних оконных occupancy недостаточно для восстановления всех per-frame
последовательностей. Coordinate-dependent анализам нужны подходящие сохранённые
координаты/топология либо заранее утверждённые scalar/coordinate features;
таблицы контактов их не восстанавливают. До массового запуска зафиксируйте
выбранные будущие анализы и retention-план. Не удаляйте координатные источники
лишь на основании успешного контактового release.

## 22. Доказательства и организация 33 траекторий

На каждый run/trajectory сохраняйте точный Git SHA; wheel/dependency версии и
хеши; input manifest с размерами/хешами и явно описанным покрытием хеширования;
authority controls; argv, cwd и значимые параметры среды без секретов;
PBC diagnostics; отчёты validation; QC reviews/decisions; artifact inventory
и run provenance. Не называйте size/header fingerprint полным SHA256 DCD.
В D.2 full DCD hash не был обязательным доказательством: применялись отдельно
задокументированные bounded fingerprints и input identity checks.
Raw trajectories хранятся во внешнем хранилище, а не в Git/evidence ZIP.

Одна траектория/реплика — независимая work unit с отдельным output root.
После её науки выполняется QC; группа агрегируется после всех окончательных
решений; публикация начинается после фиксации авторитетных aggregate inputs.
Не смешивайте выходы попыток и не запускайте несколько writers в один каталог.
Оценки RAM, диска и времени из короткого пилота нельзя экстраполировать как
утверждённый ресурсный запрос для полной траектории.

Handoff охватывает концептуально **33 trajectories / 19 systems**. Этот документ
не генерирует manifests или команды для всех 33: для каждой системы могут
различаться engine/time/condition controls и наборы партнёров. Проверенные
manifest identities и retention-план должны существовать до массового запуска.

**TO BE VERIFIED IN STAGE 34.E:** фактическое получение кода/окружения на кластере,
совместимость wheelhouse, пути и доступ к хранилищу, ограничения ресурсов,
настройки параллелизма, утверждённый per-system orchestration adapter,
отправка/наблюдение/возобновление заданий, доставка и сохранение evidence.
Ни одна кластерная команда этим руководством не заявлена проверенной.

## 23. Когда остановиться

| Ситуация | Действие |
| --- | --- |
| Не тот Git SHA или dirty checkout | Восстановить правильный чистый источник, не смешивать сборки |
| Импорт/executable из чужой среды | Исправить окружение и повторить isolation checks |
| Нет authority file или не совпал хеш | Получить правильный утверждённый control, не угадывать значение |
| Не разрешено physical time или mapping неполон | Остановить scientific publication до разрешения источников |
| Существенное PBC несоответствие | Сохранить диагностику; исправление/повтор требуют подтверждённого протокола |
| `<95%` expected production samples | Применить hard-QC exclusion; не уменьшать requested interval ради PASS |
| Обязательный REVIEW не разрешён | Получить привязанное решение; не агрегировать pending population |
| Запрошен specialized aggregate без correspondence | Не создавать его; допустим только явно согласованный header-only scope |
| F1/F2 или cross-table failure | Разобрать source/identity/metric mismatch; не обходить валидатор |
| `partial` либо `complete=false` | Завершить bindings/проверки; код 0 сам по себе недостаточен |

При отказе сохраняйте исходную попытку, команды и вывод. Новую попытку пишите
в новый output root с текущим provenance; не чините вручную frozen science.
