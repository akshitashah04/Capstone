# Fifty fictional student searches: results

## What we ran

We wrote [50 fictional student profiles](../../evaluation/personas/student-personas.jsonl) before seeing any results: 25 undergraduates and 25 graduate students in 50 different programs. Each has a study goal, a reading need, and a query in the student's voice. Forty questions are in English, four in Spanish, four in French, and two in German. These are authored scenarios, not questions collected from NYU students or real personal profiles.

The [cloud search run](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/43776657495) passed on 2026-11-15. It used the project's pinned 91,667-book DOAB index and ran keyword, semantic, and hybrid search on the same 50 questions. The full top-ten result files are preserved as a [605 KB ZIP](../../evaluation/personas/search-run-99e564e.zip) in Git and as a [GitHub artifact](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/43776657495/artifacts/14186453565) through 2026-12-15. The [manifest](../../evaluation/personas/search-run-manifest.json) records the exact question hash, index revision, result checksums, and 1,113 distinct question–book pairs. The full catalog and search index were used only on a temporary GitHub runner.

We independently judged the union of each mode's first five books for each student: **599 distinct question–book pairs**. A book received `0` if it was off topic or unusable, `1` if related but incomplete or its reading level was unclear, and `2` only when the preview clearly supported both the study goal and reading need. We graded 199 as `0`, 359 as `1`, and 41 as `2`. Among 129 topically strong pairs, 41 had clear reading-level fit, 54 had unclear fit, and 34 had a clear mismatch. Sixty-nine of the 599 pairs had no abstract preview. These are [assistant judgments](../../evaluation/personas/ai-labels.csv), not student or librarian judgments.

## Which search did better?

| Measure, 50 questions | Keyword | Semantic | Hybrid |
| --- | ---: | ---: | ---: |
| Clear topic **and** reading-level fit in top five | 11 (22%) | 14 (28%) | **15 (30%)** |
| Clear fit at rank one | 3 (6%) | **8 (16%)** | 7 (14%) |
| Strong topic match in top five, even if level is wrong or unclear | 21 (42%) | **28 (56%)** | **28 (56%)** |
| Graded ordering within the judged top-five pool, nDCG@5 | 0.5007 | 0.7191 | **0.7448** |
| Warm-search p95 on the GitHub runner | 143 ms | **54 ms** | 172 ms |

**Hybrid edges semantic on the main top-five measure by one student, 15 to 14, and has slightly better nDCG@5. Semantic has more clearly suitable books at rank one, is faster in this runner, and does better for graduate scenarios (8 of 25 versus hybrid's 6 of 25). Hybrid does better for undergraduates (9 of 25 versus semantic's 6 of 25). This is a close result, not a decisive winner.** Keyword is weaker on all relevance measures here.

The nDCG score measures order among books already found by at least one mode and gives some credit to partly useful books. A high nDCG can coexist with no clearly suitable book. This study grades only the top five; its nDCG@5 **cannot** be compared with the project's provisional nDCG@10 target. The provisional 80% Success@5 bar is not reached numerically by any mode here. No known-title question was tested. Warm timing excludes loading the model/index and any future user interface.

The language slices are small. Hybrid found a clear fit for 14 of 40 English questions and one of two German questions, but none of the four Spanish or four French questions. Those eight failures deserve direct review of both corpus coverage and ranking; they do not prove a general language failure. Many queries also ask for a combination of subject, method, region, and level that may not exist in this DOAB snapshot.

## Examples that explain the scores

- A business undergraduate asked for AI without coding. Hybrid put **Business Data Ethics** first, and the preview discusses responsible AI in business organizations. Semantic's first result, **Big Data and Artificial Intelligence**, had no abstract showing its level or business examples.
- An anthropology undergraduate asked about Indigenous data sovereignty. All three modes put a directly relevant book first.
- An urban-studies undergraduate asked about affordable housing policy. Semantic put **Evidence and Innovation in Housing Law and Policy** first; hybrid did not put a clearly suitable book in its top five.
- A graduate architecture student asked for coastal flood adaptation cases. Semantic found two useful guides in the top three; hybrid missed both in its top five.
- A Spanish political-science student asked for an introduction to proportional representation. The returned books used “representation” in broader political senses and did not clearly explain electoral systems.
- A computer-science graduate student asked how to evaluate retrieval-augmented generation. No top-five result clearly covered retrieval metrics or grounded-answer evaluation.
- A German finance graduate student asked about climate risk in bank lending and regulation. All three modes ranked **Integrating Climate Risks in Bank Risk Management and Capital Requirements** first.

## All 50 outcomes

The [50-row findings file](../../evaluation/personas/persona-findings.csv) contains every query, the first book returned by each mode, the rank of the first clearly suitable book in each mode, a representative book and source link, and a short finding. The [scored JSON](../../evaluation/personas/persona-metrics.json) also gives per-persona nDCG and grouped measures. A blank strong-match rank means no clearly suitable book appeared in that mode's top five; it does not mean every returned book was unrelated.

| Student | Level and program | First clear fit, K / S / H | Finding |
| --- | --- | --- | --- |
| 01 | Undergrad, Business | 5 / — / 1 | Business Data Ethics has company examples without coding; other AI books are more technical or unrelated. |
| 02 | Undergrad, Biology | — / 3 / 2 | The CRISPR-Cas9 textbook is a clear starting point; many alternatives are specialist article collections. |
| 03 | Undergrad, History | — / — / — | No clear beginner history of ordinary people in the French Revolution appeared; results focus on specialist themes. |
| 04 | Undergrad, Economics | — / — / — | No introductory inflation explanation appeared; several results drift to unrelated economics or family topics. |
| 05 | Undergrad, Psychology | — / — / — | Anxiety titles emphasize clinical research rather than simple evidence on treatment choices. |
| 06 | Undergrad, Computer Science | 1 / 1 / 1 | Accessible AI ethics books explain bias with concrete examples. |
| 07 | Undergrad, Nursing | — / — / — | Diabetes results emphasize clinical mechanisms, not patient-facing education. |
| 08 | Undergrad, Architecture | — / 2 / 2 | Urban Heat Island Mitigation Technologies discusses climate-sensitive design; the available preview does not confirm diagrams. |
| 09 | Undergrad, Political Science | — / — / — | Spanish results treat representation broadly; none clearly explains proportional voting systems. |
| 10 | Undergrad, English Literature | — / — / — | Postcolonial results are advanced scholarship or unrelated; no beginner reading path is clear. |
| 11 | Undergrad, Environmental Science | 5 / — / 4 | Marine Pollution: Monitoring, Management and Mitigation is practical and readable; some plastic books are narrower. |
| 12 | Undergrad, Music | — / — / — | No clear guide to jazz origins and communities appeared; the closest books focus on narrower settings. |
| 13 | Undergrad, Anthropology | 1 / 1 / 1 | Indigenous Data Sovereignty books directly explain community control of data. |
| 14 | Undergrad, Film Studies | — / — / 1 | Development of the Global Film Industry discusses Netflix and changes in film production. |
| 15 | Undergrad, Mathematics | — / — / — | No beginner guide to interpreting surveys appeared; results cover other statistics topics. |
| 16 | Undergrad, Chemistry | — / — / — | German battery results are specialist electrochemistry rather than a clear introduction. |
| 17 | Undergrad, Journalism | — / — / — | Misinformation books discuss policy or theory; no hands-on reporting method is clear. |
| 18 | Undergrad, Urban Studies | 4 / 1 / — | Evidence and Innovation in Housing Law and Policy is accessible; hybrid missed clear housing-policy books in its top five. |
| 19 | Undergrad, Education | — / 2 / 5 | Multilingualism in the Classroom and Critical Consciousness in Dual Language Education affirm home languages with cases. |
| 20 | Undergrad, Philosophy | — / — / — | French free-will books address the topic, but beginner suitability is unclear from the previews. |
| 21 | Undergrad, Public Health | — / — / — | Local public-health books cover organization or outreach, but not outbreak communication case studies. |
| 22 | Undergrad, Art History | — / — / — | French results cover women writers or museums separately, not overlooked women artists and their works. |
| 23 | Undergrad, Data Science | — / — / — | Visualization results do not clearly teach how to spot misleading charts without coding. |
| 24 | Undergrad, International Relations | — / — / — | Spanish results mix migration and other policies; none clearly covers migration to Europe and tested responses. |
| 25 | Undergrad, Physics | 4 / — / 2 | Quantum Computing for the Quantum Curious uses minimal math; the business introduction also explains possibilities and limits. |
| 26 | Graduate, MBA | — / 2 / — | A Guide to Sustainable Corporate Responsibility gives practical cases; greenwashing tests are less explicit. |
| 27 | Graduate, Public Administration | — / — / — | Transit results discuss transport or displacement, but not fare and service-cut evidence together. |
| 28 | Graduate, Public Health Practice | — / — / — | Vaccine books explain campaigns and politics, not tested outreach methods for distrust. |
| 29 | Graduate, Computer Science Research | — / — / — | No technical RAG-evaluation book appeared; results drift into broad NLP and unrelated topics. |
| 30 | Graduate, Sociology | 2 / 1 / 2 | Several scholarly platform-work books cover labor conditions and collective bargaining. |
| 31 | Graduate, Advanced Nursing | — / — / — | Caregiver titles are general or in Portuguese; no clear evidence-based dementia home-care guide appeared. |
| 32 | Graduate, Special Education | — / — / — | Spanish results cover education broadly; none clearly studies interventions for reading difficulties. |
| 33 | Graduate, Architecture and Resilience | — / 2 / — | Climate Adaptation and Resilience Across Scales and Coastal Cities offer design guidance; hybrid missed them in its top five. |
| 34 | Graduate, Caribbean History | — / — / — | Caribbean history and archive-method topics appear separately; no combined thesis guide is clear. |
| 35 | Graduate, Law | — / — / — | AI law books focus on Europe or general risk; none clearly compares US and EU training-data privacy. |
| 36 | Graduate, Applied Economics | — / — / — | No difference-in-differences methods book appeared; results mostly cover unrelated policy subjects. |
| 37 | Graduate, Linguistics | — / — / — | French 'alternance' pulled political alternation, not classroom code-switching. |
| 38 | Graduate, Environmental Engineering | — / — / — | Water-treatment books mention membranes or adsorption but not a PFAS comparison with costs and limits. |
| 39 | Graduate, Social Work | — / 1 / — | Interprofessional Approach to Refugee Health offers practical culturally responsive guidance. |
| 40 | Graduate, Biostatistics | — / — / — | No clinical-trial missing-data text appeared; results are general statistics or unrelated. |
| 41 | Graduate, Creative Writing | — / — / — | Memoirs appear as examples, not craft guidance on nonlinear structure and voice. |
| 42 | Graduate, Media Studies | — / 1 / 3 | Democratic Algorithms and Living with Algorithms study recommenders and their social effects. |
| 43 | Graduate, Food Studies | 2 / — / 1 | The results cover urban food access, school food banks, and community food sharing with cases. |
| 44 | Graduate, Global Affairs | — / — / — | Spanish results discuss climate and migration separately, not climate migration with adaptation policy. |
| 45 | Graduate, Biomedical Engineering | 5 / 2 / 5 | Assistive-technology and rehabilitation books cover robot design and outcome evaluation. |
| 46 | Graduate, Religious Studies | — / — / — | Religious ecology books discuss practice, but a Buddhism-specific text-to-practice fit is unclear. |
| 47 | Graduate, Cybersecurity Policy | 3 / 1 / 1 | Indigenous Data Sovereignty books address ownership and governance; technical access-control detail needs checking. |
| 48 | Graduate, Museum Studies | — / — / — | French museum books cover collections or Indigenous objects, not restitution decisions and community views. |
| 49 | Graduate, Applied Psychology | — / — / — | Workplace wellbeing books discuss risk factors; clear intervention evidence for healthcare burnout is missing. |
| 50 | Graduate, Sustainable Finance | 1 / 1 / 1 | Integrating Climate Risks in Bank Risk Management directly covers European bank practice and regulation in German. |

## Judgment and next work

The new evidence changes the earlier diagnostic picture: answer-derived questions favored semantic search, while these more varied student-style scenarios give hybrid a narrow top-five lead. The engine often finds a relevant **topic**, but it is much less reliable at meeting the student's stated reading level and purpose. I would keep both semantic and hybrid available for the prototype and avoid claiming either is a dependable default yet. The immediate improvement to test is ranking that pays more attention to explicit constraints such as “beginner,” “no coding,” “case studies,” and “graduate methods.” The next evaluation should involve people reading selected books, natural anonymous student questions, and a held-out comparison after any ranking change.

This result is a **diagnostic**, not an official KPI pass. The assistant wrote the scenarios and graded short metadata previews, so the judgments can be wrong. A book with no abstract may be useful despite an uncertain grade. We did not inspect full book contents or establish that any book actually solves a student's assignment. The search scores are relative ranking numbers, not confidence probabilities.
