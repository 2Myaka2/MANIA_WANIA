# Ramila GROMACS: запуск production v2 в Colab

Используйте точный тег `ramila-production-v2`. Для клонирования по HTTPS Андрей
должен сначала опубликовать этот тег в GitHub: в текущем checkpoint тег создан
только локально, без push. Не подменяйте его другой версией.

Нужны все 12 окончательных XTC и соответствующие принятые TPR/MDP/LOG.
Источники: WT `eqmd_rep100ns_09_2026` (100 нс), T330M `T330M_30ns_09_2026`
(30 нс). Сохраните дерево `VARIANT/CONDITION/replica N/`, включая пробел
в `replica 1`. Имена XTC: `md_repN_full.xtc` для WT, `t330m_repN.xtc` для T330M.
Исторические phase1 и `30ns_03-2026` не заменяют эти источники.

## 1. Получить версию и установить

Выберите Colab с Python 3.12. После публикации тега выполните в отдельной ячейке:

```bash
%%bash
set -euo pipefail
cd /content
git clone https://github.com/2Myaka2/MANIA_WANIA.git
cd MANIA_WANIA
git checkout --detach ramila-production-v2
git rev-parse HEAD
python --version
python -m pip install 'numpy==2.0.2' '.[science]'
mania --version
```

Сравните SHA с итоговым отчётом Андрея. Conda не нужна.

## 2. Подключить Drive и задать пути

```python
from google.colab import drive
drive.mount('/content/drive')

import os, sys, subprocess
from pathlib import Path
SOURCE_ROOT = '/content/drive/MyDrive/Ramila'
OUTPUT_ROOT = '/content/drive/MyDrive/Ramila_MANIA_v2_results'
os.chdir('/content/MANIA_WANIA')
```

`SOURCE_ROOT` содержит `WT/` и `T330M/`. Для v2 используйте новый `OUTPUT_ROOT`,
который не находится внутри источников и не содержит их. Нужны достаточный
объём хранилища и время для полной подготовки; временные координаты тоже
пишутся в выходной каталог. MANIA оценивает свободное место до подготовки.
Исходные файлы сохраняются неизменными.

## 3. Один раз подтвердить источники

```python
sys.path.insert(0, 'tools')
from run_ramila_gromacs import init
init(Path(SOURCE_ROOT), Path(OUTPUT_ROOT), input_fn=input)
```

Проверьте все 12 строк XTC → TPR → MDP → LOG. Введите своё имя, заметку проверки
и `y` в ответ на `Approve? y/N`. Это подтверждает только соответствие источников
наборам запусков; PBC и научный QC требуют отдельных проверок. Хеши вычисляет
программа. При отсутствии любого окончательного XTC init блокируется.
После изменения источников или версии нельзя продолжать со старым подтверждением.

## 4. Запустить одну траекторию или последовательную группу

```python
subprocess.run(
    ['./run_ramila_gromacs_one.sh', SOURCE_ROOT, OUTPUT_ROOT,
     'gromacs_wt_norm_r1'], check=True)
```

Идентификатор имеет вид `gromacs_wt_norm_r1` или `gromacs_t330m_tumor_r3`:
вариант `wt`/`t330m`, условие `norm`/`tumor`, реплика `r1`/`r2`/`r3`.
Для последовательного запуска выберите одну из команд:

```python
subprocess.run(['./run_ramila_wt_all.sh', SOURCE_ROOT, OUTPUT_ROOT], check=True)
# либо ./run_ramila_t330m_all.sh, либо ./run_ramila_gromacs_all.sh
```

Параметры уже заданы: production 5–100 нс для WT и 5–30 нс для T330M,
отсчёты каждые 200 пс, включительные окна длиной 2 нс с шагом 1 нс.
JSON и научные параметры редактировать не нужно. Подготовка сохраняет полную
временную ось: разворачивание связанных фрагментов → центрирование белка →
оборачивание целых фрагментов, XTC:4. Внутренний MIC выключен.

MANIA автоматически сохраняет белковые, липидные и гликановые наблюдения,
канонические таблицы, проверки и точный replay. Завершённый результат повторно
проверяется перед использованием; незавершённые попытки остаются под отдельными
номерами. Пропуски не интерполируются и не заменяются соседними кадрами;
при разрешении менее 95% ожидаемых production-отсчётов QC завершается ошибкой.

## 5. RMSD и последующий научный review

RMSD создаётся автоматически в том же проходе выбранных белковых contact-кадров,
из тех же PBC-подготовленных координат. Используется по одному явно сопоставленному
Cα на присутствующий остаток, в каноническом порядке; выравнивание — float64,
равные веса, центрирование и Kabsch с правильным вращением, единицы Å.
Фиксированный reference — первый разрешённый запрошенный production-отсчёт;
стабилизация в RMSD v1 не входит. Отдельного чтения траектории только ради RMSD нет.

В завершённой попытке сохранены:
`preprocessing/protein_rmsd_timeseries.csv` и
`preprocessing/protein_rmsd_measurement.json`.
Для просмотра без координат укажите путь завершённой попытки из поля `output`
в результате запуска:

```python
ATTEMPT_ROOT = f'{OUTPUT_ROOT}/trajectories/gromacs_wt_norm_r1/attempt_0001'
# Замените номер на фактически завершённую попытку из результата запуска.
subprocess.run(
    ['mania', 'production', 'review-rmsd', '--output-root', ATTEMPT_ROOT],
    check=True)
```

Просмотр показывает reference, отсчёты и значения RMSD и требует явного научного
assessment позже. Автоматического порога или классификации drift нет.
Значения RMSD сами по себе не означают `drift_detected=false` или QC PASS.
Наблюдения целостности связанного белка сохранены отдельно;
`scientific_pbc_status=unresolved` не превращается в общую сертификацию PBC.
Агрегация реплик выполняется позже, после явного production QC и review.

## 6. Что сохранить и вернуть Андрею

**Не удаляйте `OUTPUT_ROOT`**, включая отчёты подготовки и незавершённые попытки.
Верните SHA тега, журнал запуска, перечень завершённых trajectory/attempt и
`source_attestation.json`. Для каждой завершённой попытки передайте компактные
`preprocessing/`, `evidence/`, `handoff/`, `inputs/preprocessing.json`,
`request.json`, `acceptance.json`, `science_complete.json` и
`handoff_complete.json`. В `inputs/` дополнительные маленькие controls также
можно сохранить. Это самостоятельный handoff для обычного QC, проверки,
покадрового replay и RMSD review только из OUTPUT_ROOT.

Многогигабайтные raw/prepared XTC и scratch не включайте в компактный архив.
Подготовленную траекторию не требуется возвращать только ради обычного QC;
сохраните её у себя для возможных последующих расчётов с координатами.

Production execution готов. Полная биологическая аннотация Ramila остаётся
**PENDING** для WT-NORM, WT-TUMOR, T330M-NORM и T330M-TUMOR. Полные аннотированные
публикационные результаты ожидают подтверждения владельца. Наблюдения TPR
не заменяют это подтверждение; аннотации Egor не переносятся.
