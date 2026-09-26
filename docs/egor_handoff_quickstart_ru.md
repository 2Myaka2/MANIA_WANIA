# MANIA: запуск одной траектории Егора

**CPython 3.12 · Linux x86_64 · glibc ≥ 2.28.** Нужны Bash, Git с доступом к
репозиторию, Python с `venv`, свободный диск и стабильные UTC/NTP. Wheelhouse не
подходит для Windows/macOS/ARM/другого Python. Распакуйте ZIP в `$HOME/mania-input/`.
Свои raw DCD, PSF/CONF/OUT/XSC и общий `egor/toppar/` разместите относительно этого
каталога по `SOURCE_PATHS.tsv`. Их нет в ZIP. При необходимости замените пути ниже.
Блоки выполняются по порядку в одной Bash-сессии; **при ошибке остановитесь**.

**1. Получить точный код.** MANIA будет установлена из этого checkout.
```bash
set -euo pipefail
unset PYTHONPATH
git clone git@github.com:2Myaka2/MANIA_WANIA.git "$HOME/mania-code"
cd "$HOME/mania-code"
git checkout --detach aa24f04900767b04f1303be18fe867e879feea93
test "$(git rev-parse HEAD)" = aa24f04900767b04f1303be18fe867e879feea93
```
**2. Новое окружение; установка только из локальных wheels.** Онлайн-путь pip
при проверке не сработал. Успех: все команды — код 0, MANIA `0.1.0` из
`mania-code/src/mania`, MDAnalysis `2.10.0` из новой `.venv`.
```bash
DELIVERY="$HOME/mania-input/egor_delivery_aa24f0490076"
python3.12 -m venv .venv
source .venv/bin/activate
export PIP_NO_INDEX=1 PIP_FIND_LINKS="$DELIVERY/wheelhouse"
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e '.[md]'
python -m pip check
mania --version
python -c 'import mania, MDAnalysis as m; print(mania.__file__); print(m.__version__,m.__file__)'
```
**3. Одна траектория, новые пути попытки.** Для другой реплики возьмите её ID из
`SOURCE_PATHS.tsv`. `RESULT_ROOT` внутри data root, `OUTPUT_ROOT` вне него.
Не создавайте `RESULT_ROOT` заранее; для новой попытки меняйте суффикс.
```bash
export MANIA_DATA_ROOT="$HOME/mania-input"
HANDOFF="$DELIVERY/egor_handoff"
TRAJECTORY_ID=namd_egor_wt_0ss_r1
RESULT_ROOT="$MANIA_DATA_ROOT/prepared/${TRAJECTORY_ID}_attempt_001"
OUTPUT_ROOT="$HOME/mania-results/${TRAJECTORY_ID}_attempt_001"
LOG_DIR="$HOME/mania-logs/${TRAJECTORY_ID}_attempt_001"
mkdir -p "$(dirname "$LOG_DIR")"
mkdir "$LOG_DIR"
```
**4. Проверить пакет.** Успех: все checksums — `OK`; checker — `PASS`, `rows=9`,
`systems=3`. Это проверка пакета; исходные координаты проверит prepare.
```bash
(cd "$DELIVERY" && sha256sum -c DELIVERY_FILES.sha256)
(cd "$HANDOFF" && sha256sum -c HANDOFF_FILES.sha256)
python -B "$HANDOFF/check_package.py"
```
**5. Подготовить одну полную траекторию.** 12 GB — порог свободного места,
не резервирование и не оценка размера всех результатов. Успех: `pending_review`.
```bash
python tools/prepare_production_inputs.py prepare \
  --data-root "$MANIA_DATA_ROOT" --result-root "$RESULT_ROOT" \
  --authority-package "$HANDOFF" --trajectory-id "$TRAJECTORY_ID" \
  --min-free-bytes 12000000000 --workers 1 --threads 1 >"$LOG_DIR/prepare.log" 2>&1 \
  && echo 0 >"$LOG_DIR/prepare.exit" || { echo $? >"$LOG_DIR/prepare.exit"; exit 1; }
cat "$LOG_DIR/prepare.log"
cat "$RESULT_ROOT/summary.txt"
```
**6. СТОП: человеческое ревью.** Нужны все 12 автоматических `PASS`, без failures.
Прочитайте `summary.txt` и отчёт. Проверьте raw DCD ↔ PSF ↔ выбранный запуск по
происхождению и CONF/OUT/сопутствующим файлам. DCD не содержит меток атомов:
совпадение числа атомов само по себе не доказывает их физический порядок.
Без ревью дальше не идти; старое одобрение не переносить.

**7. Только после ревью подтвердить.** Введите настоящее имя, основание одобрения
и SHA256 из вывода **этой** подготовки. JSON, наблюдения и hashes не редактировать.
```bash
read -r -p 'Имя проверившего: ' REVIEWER
read -r -p 'Что проверено, основание одобрения: ' REVIEW_NOTE
read -r -p 'SHA256 проверенного отчёта: ' REPORT_SHA256
python tools/prepare_production_inputs.py confirm \
  --data-root "$MANIA_DATA_ROOT" --result-root "$RESULT_ROOT" \
  --authority-package "$HANDOFF" --trajectory-id "$TRAJECTORY_ID" \
  --report-sha256 "$REPORT_SHA256" --reviewer "$REVIEWER" --review-note "$REVIEW_NOTE" \
  --approve --production-output-root "$OUTPUT_ROOT" --min-free-bytes 12000000000 \
  >"$LOG_DIR/confirm.log" 2>&1 \
  && echo 0 >"$LOG_DIR/confirm.exit" || { echo $? >"$LOG_DIR/confirm.exit"; exit 1; }
cat "$LOG_DIR/confirm.log"
```
Успех: `binding_materialized`. Вывод и `confirmation/commands.json` содержат две
готовые команды. Ниже те же команды через переменные сессии, с записью логов.

**8. Сгенерированный validate.** Успех: `preflight_passed`, `READY`, код 0.
```bash
env MANIA_DATA_ROOT="$MANIA_DATA_ROOT" mania production validate \
  --catalog "$HANDOFF/catalog/dataset.yaml" --trajectory-id "$TRAJECTORY_ID" \
  --output-root "$OUTPUT_ROOT" \
  --input-binding "$RESULT_ROOT/confirmation/production_input_binding.json" \
  --min-free-bytes 12000000000 >"$LOG_DIR/validate.log" 2>&1 \
  && echo 0 >"$LOG_DIR/validate.exit" || { echo $? >"$LOG_DIR/validate.exit"; exit 1; }
cat "$LOG_DIR/validate.log"
```
**9. Сгенерированный ПОЛНЫЙ run: 5–100 ns.** Шаг 200 ps, окна 2 ns через 1 ns:
476 отсчётов, 94 окна по 11 при полной доступности. Technical manifest не добавлять.
```bash
env MANIA_DATA_ROOT="$MANIA_DATA_ROOT" mania production run \
  --catalog "$HANDOFF/catalog/dataset.yaml" --trajectory-id "$TRAJECTORY_ID" \
  --output-root "$OUTPUT_ROOT" \
  --input-binding "$RESULT_ROOT/confirmation/production_input_binding.json" \
  --min-free-bytes 12000000000 >"$LOG_DIR/run.log" 2>&1 \
  && echo 0 >"$LOG_DIR/run.exit" || { echo $? >"$LOG_DIR/run.exit"; exit 1; }
cat "$LOG_DIR/run.log"
```
Успех: `science_complete`, код 0 и `science_complete.json` в
`$OUTPUT_ROOT/trajectories/$TRAJECTORY_ID/`.

**10. Передать Андрею целиком `$OUTPUT_ROOT`, `$RESULT_ROOT`, `$LOG_DIR`.** Сохранить
структуру, подготовленный DCD, подтверждение и артефакты, не только CSV. Логи команд
и exit status: `$LOG_DIR/*.log`, `*.exit`. Подробные журналы подготовки/подтверждения:
`operation.log`, `phases.jsonl`, `operation.json` в `$RESULT_ROOT` и `confirmation/`
(в JSON — время и код выхода). При ранней ошибке смотрите `$LOG_DIR`;
после сбоя сохраните попытку и сообщите Андрею.

> Автоматический PASS не заменяет человеческое одобрение. `science_complete` не
> означает финальный QC/публикацию. Реплики пока не агрегировать. Не перезаписывать
> неудачные/неполные попытки. `--resume` использует завершённые стадии, но не
> продолжает незаконченный расчёт контактов с середины. После prepare входы не перемещать.

Ранее проверены полный prepare 0SS/r1, технический run 5–8 ns, replay без геометрии
и resume. Полный run 5–100 ns ещё предстоит. Для 1SS/r1 доказаны только выбор своих
topology/controls и applicability первого кадра; полная подготовка 1SS не проверена.
Справка: [production interface](egor_production_interface.md),
[подготовка и подтверждение](production_input_preparation.md).
