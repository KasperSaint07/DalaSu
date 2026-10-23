# 10. Project Management and Risks

## 1. Team and roles

| Person | Role |
|---|---|
| Madiyar Amanzhol | Developer, backend and model evaluation |
| Aldiyar Amangeldi | Developer, ML and mobile application |
| Kuralay Makhmetova | Supervisor |

Areas of responsibility are described in [01](01-project-proposal.md).

## 2. Task tracking

Tasks are tracked in YouTrack, project **DalaSu** (key `DAL`): https://dalasu.youtrack.cloud/projects/DAL

The project has 20 tasks. At the time of submission, 19 are resolved and 1 is open (DAL-20). Titles are shortened by YouTrack where they end with "…".

| ID | Title | Assignee | Priority | State |
|---|---|---|---|---|
| DAL-1 | Скачать и изучить данные AmeriFlux … | Aldiyar | Critical | Resolved |
| DAL-2 | Собрать дневной датасет daily.csv и … | Aldiyar | Critical | Resolved |
| DAL-3 | Обучить RF и XGBoost (ML-only) с tim… | Aldiyar | Critical | Resolved |
| DAL-4 | Свести результаты фазы 1 и написат… | Aldiyar | Critical | Resolved |
| DAL-7 | Реализовать FAO-56 Penman-Monteit… | Madiyar | Critical | Resolved |
| DAL-8 | Посчитать метрики FAO-56 baseline … | Madiyar | Serious | Resolved |
| DAL-9 | Написать модуль оценки (evaluation) | Madiyar | Serious | Resolved |
| DAL-10 | Proposal | Madiyar | Normal | Resolved |
| DAL-11 | Договориться о 3–5 обсуждениях с п… | Madiyar | Critical | Resolved |
| DAL-13 | Literature review | Aldiyar | Normal | Resolved |
| DAL-14 | Existing systems comparison | Madiyar | Normal | Resolved |
| DAL-15 | Technology comparison | Aldiyar | Normal | Resolved |
| DAL-16 | Requirements | Madiyar | Normal | Resolved |
| DAL-17 | Diagrams | Aldiyar | Normal | Resolved |
| DAL-18 | UX и prototype | Aldiyar | Normal | Resolved |
| DAL-19 | Project management | Madiyar | Critical | Resolved |
| DAL-20 | Утвердить Research Question для ста… | makhmet.kb | Serious | **Open** |
| DAL-21 | Review Project Proposal | makhmet.kb | Normal | Resolved |
| DAL-22 | final review before predefense | makhmet.kb | Normal | Resolved |
| DAL-23 | edit Формы вопрос для relevance | makhmet.kb | Critical | Resolved |

## 3. Git conventions

| Item | Convention |
|---|---|
| Branch | `DAL-<n>-<short-name>` |
| Commit | `DAL-<n>: <description>` |
| Pull request | Refers to the task ID, describes how the change was checked, reviewed by the other team member |
| Submission | Git tag per submission; this one is `prob-period-1` |

## 4. Risks

Risks come from the project plan and from the findings in [09](09-verification-and-evaluation-plan.md).

| # | Risk | Effect | Response |
|---|---|---|---|
| R1 | No pilot agreement or field data in Kazakhstan yet (a letter of interest from К/Х «Арман» has been received) | No field validation; stage 2 is qualitative only | Conclude a pilot agreement with К/Х «Арман», or look for a university plot (AITU, KATU) or another farm; three survey respondents agreed to tell more |
| R2 | The vegetation season in the south starts before the defence | Field data cannot be postponed to the end of the semester | Start the search for a field early |
| R3 | One validation station (US-Ne2, USA) | Result may not transfer to Kazakhstan | State it as a limit; qualitative check against NDVI |
| R4 | ML inputs (tower net radiation, wind at 6.2 m) are not available in the app | Accuracy in the product is unknown | Test models with Open-Meteo inputs |
| R5 | Target is actual ET, baseline is ET₀ without Kc (D-1) | The gap to ML is overstated | Add baseline B2 (ETc) |
| R6 | FAO-56 Kc values are global, not calibrated to local varieties | Systematic error | Stated as a limit |
| R7 | Cloud cover reduces NDVI updates; Sentinel-2 delay about 5 days | Missing satellite correction | Fallback to FAO-56 when the image is older than five days |
| R8 | Hybrid model is required by NFR-02 but not yet implemented | Mismatch between requirement and result | Align the requirement text with the implemented ML-only models |
| R9 | XGBoost retraining differs by up to 0.003 mm/day in MAE | Small difference in reproduced metrics | Documented tolerance |
| R10 | Only 8 survey responses, 3 of 8 from the south | Evidence of relevance is limited | Further interviews |

## 5. Dependencies

- Open-Meteo, Sentinel-2 (Google Earth Engine), SoilGrids: free external sources; availability is outside the team's control.
- AmeriFlux US-Ne2: open data, already downloaded and processed (`data/`).
- Supervisor feedback: see [11](11-supervisor-feedback.md).
