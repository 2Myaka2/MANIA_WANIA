# Егор: запуск MANIA для девяти траекторий

**Версия кода: `e3f69331f95a42d1da5d0cf7d6a60646421b8079`.**
Нужны этот commit, `egor_FINAL_e3f69331f95a.zip` и эта памятка.
ZIP содержит `egor_handoff/`, controls, authority, templates и каталог;
исходных и подготовленных DCD в нём нет. Ничего из ZIP поверх checkout
копировать не нужно. Каталог и справочный `egor_production_interface.md`
взяты из указанного commit; эта новая памятка поставляется отдельно и в ZIP.

## 1. Установка и размещение

В локальном клоне репозитория, с Python ≥3.11:

```bash
cd MANIA_WANIA
git fetch origin
git checkout --detach e3f69331f95a42d1da5d0cf7d6a60646421b8079
git rev-parse HEAD
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e ".[md]"
mania --version
export MANIA_DATA_ROOT=/absolute/path/to/mania_inputs
OUTPUT_ROOT=/absolute/path/to/mania_results/attempt_01
mkdir -p "$MANIA_DATA_ROOT" "$OUTPUT_ROOT"
unzip /absolute/path/to/egor_FINAL_e3f69331f95a.zip -d "$MANIA_DATA_ROOT"
```

Заменить три абсолютных пути своими; входной и выходной корни не должны
содержать друг друга. Распаковывать в новое место, без перезаписи.
Логически есть **0SS/1SS/2SS × r1/r2/r3**; ID:
`namd_egor_wt_0ss_r1` … `namd_egor_wt_2ss_r3`. Каждой строке нужны
её собственные **DCD, PSF, CONF, OUT, XSC** и общий проверенный toppar.
Физические пути сохраняют исходные имена из `authority/source_inventory.json`:

```text
mania_inputs/
  egor_handoff/                 распакованный пакет, helpers и templates
  egor/                        PSF/CONF/OUT/XSC всех девяти строк
    *.dcd                      два известных NPT DCD: 0SS/r1, 1SS/r1
    dcd/*.dcd                  семь остальных объявленных DCD
    toppar/                    общие 57 файлов источников
  prepared/TRAJECTORY_ID/       отдельный полный подготовленный DCD
  reviewed/TRAJECTORY_ID/       raw_time.json, prepared_time.json,
                               pbc_evidence.json, site_review.json
```

0SS соответствует `MD_no_bonds_*`, 1SS — `MD_303_350_*`, 2SS —
`MD_2_bonds_*`; r1 без суффикса, r2/r3 с `_2`/`_3`.
Точные имена брать из manifest, включая различия `NPT` и `dcd/`.
PSF/CONF/OUT/XSC и toppar должны лежать по указанным путям; иной путь DCD
разрешён только через явно проверенный `site_review`, без правки каталога.

```bash
(cd "$MANIA_DATA_ROOT/egor_handoff" && sha256sum -c HANDOFF_FILES.sha256)
python "$MANIA_DATA_ROOT/egor_handoff/check_package.py"
```

Ожидается `PASS`, 9 строк, 3 системы. Проверка пакета не подтверждает
локальные DCD или качество PBC. При ошибке остановиться и передать лог Андрею.

## 2. Подготовить одну строку

Выбрать, например, `TRAJECTORY_ID=namd_egor_wt_0ss_r1`; для каждой следующей
строки повторить весь review независимо. Подробности и схемы — в `README.md`
пакета, `templates/$TRAJECTORY_ID/` и `authority/pbc_protocol.json`.

1. Сверить SHA256/размеры своих PSF/CONF/OUT/XSC и всех toppar с authority.
   Проверить raw DCD: SHA256, связь с CONF/OUT, заголовок, все кадры/ячейки,
   физический порядок атомов и кадров. Один заголовок порядка атомов не доказывает.
2. Внешне подготовить отдельный DCD: unwrap связанных фрагментов → центрирование
   по белку → wrap целых фрагментов. Сохранить все 1000 кадров, атомный порядок,
   ячейки и полную ось 100–100000 ps; получить PBC audit с именем проверяющего.
   Старое принятие 0SS/r1 применимо только к его точным проверенным байтам.
3. Завершить два runtime time-control JSON по схеме
   `mania.namd_time_authority.v1`: абсолютные пути внутри data root, собственные
   CONF/OUT, реальные `observe_dcd` наблюдения и исходная временная ось.
   Шаблоны не являются готовыми controls; нельзя придумать `observed_times`
   или просто сменить `status`. Наблюдения первых/последнего кадров не заменяют
   проверку всех кадров/PBC; финальный XSC также её не заменяет.
4. Создать `reviewed/$TRAJECTORY_ID/site_review.json` с ровно восемью полями:
   `schema_version="egor.handoff.site_review.v1"`, `trajectory_id`,
   `raw_trajectory`, `prepared_trajectory`, `raw_time_control`,
   `prepared_time_control`, `pbc_evidence`, `prepared_lineage`.
   Пять файловых путей — относительно data root. `prepared_lineage` взять
   из `input_binding.template.json` → `payload.prepared_lineage`; заполнить
   реальные hashes, подтверждения порядка, reviewer и note после review.
   `internal_mic=false`; MANIA не исправляет PBC автоматически.

```bash
TRAJECTORY_ID=namd_egor_wt_0ss_r1
SITE_REVIEW="$MANIA_DATA_ROOT/reviewed/$TRAJECTORY_ID/site_review.json"
python "$MANIA_DATA_ROOT/egor_handoff/materialize_binding.py" \
  --data-root "$MANIA_DATA_ROOT" --trajectory-id "$TRAJECTORY_ID" \
  --site-review "$SITE_REVIEW"
INPUT_BINDING="$MANIA_DATA_ROOT/egor_handoff/site/$TRAJECTORY_ID/production_input_binding.json"
```

Ожидается `binding_materialized`. Helper не готовит DCD и не выдаёт PBC PASS;
повторную запись существующего `site/$TRAJECTORY_ID/` запрещает.

## 3. Проверить площадку и запустить 5–100 ns

Перед unattended job проверить стабильный UTC и синхронизацию NTP
(`NTPSynchronized=yes`; если systemd нет — `chronyc tracking` или проверка
администратора). При скачках часов запуск отложить. Проверить также квоту
и место для внешней подготовки. Ниже 100 GiB — пример минимального резерва,
**не оценка размера результатов**; выбрать положительный бюджет площадки.

```bash
FREE_SPACE_BUDGET=107374182400
mkdir -p "$OUTPUT_ROOT/evidence"
LOG_DIR="$OUTPUT_ROOT/evidence/$TRAJECTORY_ID"
mkdir "$LOG_DIR"
date -u > "$LOG_DIR/utc.txt"
timedatectl show -p NTP -p NTPSynchronized > "$LOG_DIR/ntp.txt"
df -B1 "$MANIA_DATA_ROOT" "$OUTPUT_ROOT" > "$LOG_DIR/disk.txt"
mania production validate \
  --catalog "$MANIA_DATA_ROOT/egor_handoff/catalog/dataset.yaml" \
  --trajectory-id "$TRAJECTORY_ID" --output-root "$OUTPUT_ROOT" \
  --input-binding "$INPUT_BINDING" --min-free-bytes "$FREE_SPACE_BUDGET" \
  > "$LOG_DIR/validate.json" 2> "$LOG_DIR/validate.stderr.log"
```

Просмотреть сохранённые UTC/NTP/disk логи. Продолжать только после exit 0 и
`preflight_passed`. `trajectory_pbc_qc_certified=false` ожидаемо: preflight
не заменяет внешний review. Затем полная production-команда:

```bash
mania production run \
  --catalog "$MANIA_DATA_ROOT/egor_handoff/catalog/dataset.yaml" \
  --trajectory-id "$TRAJECTORY_ID" --output-root "$OUTPUT_ROOT" \
  --input-binding "$INPUT_BINDING" --min-free-bytes "$FREE_SPACE_BUDGET" \
  > "$LOG_DIR/run.json" 2> "$LOG_DIR/run.stderr.log"
```

**Одна траектория за раз / один отдельный job**, остальные строки запускать
независимо с их ID, review и binding. Расчёт: **5–100 ns / 200 ps / окно 2 ns /
шаг 1 ns**, inclusive; 476 целей, 94 полных окна, 11 целей на окно.

## 4. Вернуть Андрею и ограничения

Вернуть целиком `OUTPUT_ROOT/trajectories/$TRAJECTORY_ID/`, включая
`science_complete.json`, `request.json`, `inputs/`, весь `preprocessing/`
(per-frame, canonical/annotated, provenance, inventory, validation).
Приложить stdout/stderr, exit codes, UTC/NTP/disk логи, commit и версию MANIA,
binding, оба time controls, site review, PBC audit/lineage и входные hashes.
Сохранить raw/prepared DCD для воспроизведения; их передачу согласовать отдельно.
При сбое вернуть также незавершённый output и логи.

**Нельзя:** менять 5–100 ns / 200 ps / 2 ns / 1 ns; переносить controls между
системами по аналогии; пропускать PBC review; перезаписывать готовые или
незавершённые outputs; запускать агрегацию до реальных QC decisions.
Для новой попытки нужен новый output root; старые результаты сохранить.
Реальные QC и соответствие специализированных partners остаются отдельными
условиями последующей агрегации и публикации.
