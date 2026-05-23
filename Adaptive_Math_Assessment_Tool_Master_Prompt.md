# Master Build Prompt: Adaptive Math Assessment Tool
### Version 1.0 — Full-Stack EdTech Platform with Multi-Algorithm Diagnostic Engine

---

## ROLE & CONTEXT

You are an Expert Full-Stack EdTech Developer and Educational Data Scientist specialising in psychometric algorithms and cognitive diagnostic systems. Your task is to architect and build a complete, production-grade **Adaptive Math Assessment Tool** for Indian school students (Grades 5–10, aligned to NCERT curriculum). This platform will combine Computerised Adaptive Testing (CAT), Item Response Theory (IRT), Cognitive Diagnostic Models (CDM), Bayesian Knowledge Tracing (BKT), and Deep Knowledge Tracing (DKT) into a unified, intelligently orchestrated assessment engine.

The system is **data-driven by a 5-sheet Excel workbook** (the SME Template) that populates the entire relational database. The question bank already exists in this format and must be imported via an admin panel. A sample of this Excel schema is provided below. Build everything to match it exactly.

---

## PART 1 — THE QUESTION BANK EXCEL SCHEMA (5-Sheet Format)

All questions, skill mappings, error diagnostics, and dimension tags are managed via the following 5-sheet Excel workbook. The Admin panel must parse and ingest this file to populate the database.

### Sheet 1 — `1_Skills` → DB Table: `skills`
One row per skill/topic node. Builds the **Knowledge Graph** (prerequisite chain).

| Column | Description |
|---|---|
| `skill_id` | Primary Key. e.g. `S_001` |
| `skill_name` | e.g. `Arithmetic Progression`, `Fractions`, `Linear Equations (1 Var)` |
| `grade_level` | `5`, `6`, `7`, `8`, `9`, `9-10`, etc. |
| `topic_area` | `Algebra`, `Arithmetic`, `Geometry`, `Statistics` |
| `difficulty_band` | `easy`, `medium`, `hard` |
| `prerequisite_skill_ids` | Comma-separated `skill_id`s. Blank = root node. This column defines the Knowledge Graph edges. |
| `notes` | SME remarks (e.g. "NCERT topic: arithmetic_progression") |

**Knowledge Graph Logic:** `S_012 Linear Equations (1 Var)` has `prerequisite_skill_ids` = `S_002, S_011`, meaning the engine must traverse to Basic Algebra and Integers if the student fails Linear Equations. The graph can traverse from Grade 10 all the way down to Grade 5 root nodes.

---

### Sheet 2 — `2_Questions` → DB Table: `questions`
One row per question.

| Column | Description |
|---|---|
| `question_id` | PK. Format: `ncrt_{grade}_{topic}_{nnnn}` e.g. `ncrt_5_numbers_0000` |
| `question_text` | Full question stem |
| `question_type` | `MCQ`, `WordProblem`, `ShortAnswer` |
| `word_problem_flag` | `YES` / `NO` |
| `equation_twin_id` | `question_id` of the matching equation-only version. Used by the Twin Question diagnostic. Leave blank for equation-type questions. |
| `primary_skill_id` | FK → `skills.skill_id` |
| `secondary_skill_ids` | Comma-separated additional skill IDs also tested |
| `grade_level` | `5` through `10` |
| `difficulty_band` | `easy`, `medium`, `hard` |
| `option_A` through `option_D` | MCQ answer choices |
| `correct_option` | `A`, `B`, `C`, or `D` |

---

### Sheet 3 — `3_Q_Matrix` → DB Table: `q_matrix`
Binary grid: rows = questions, columns = skills. A `1` means this question tests that skill.

| Column | Description |
|---|---|
| `question_id` | FK → `questions` |
| `difficulty_band` | Denormalised band (for fast filtering) |
| `S_001` … `S_033` | Binary `0`/`1` per skill. Each `1` becomes a row in `q_matrix: {question_id, skill_id}` |
| `Skills Tested (auto)` | Count of `1`s. Auto-calculated. Do not modify. |

The Q-Matrix powers the CDM — it tells the engine exactly which **combination of skills** a question tests so that a wrong answer can be attributed to a specific gap in that set.

---

### Sheet 4 — `4_AnswerTraps` → DB Table: `answer_traps`
One row per **wrong option** (distractors B, C, or D when A is correct, etc.). This sheet is the core of the CDM diagnostics.

| Column | Description |
|---|---|
| `question_id` | FK → `questions` |
| `option_label` | The wrong option letter (`A`, `B`, `C`, or `D`) |
| `option_text` | Exact distractor text |
| `trap_type` | Error classification: `Calculation_Error`, `Concept_Error`, `Sign_Error`, `Reading_Error`, `Procedural_Error`, `Careless_Slip` |
| `skill_gap_id` | The specific `skill_id` this wrong answer reveals (FK → `skills`) |
| `misconception` | Short label e.g. `Arithmetic Slip`, `Exponent Rule Misconception` |
| `misconception_detail` | Full explanation of the error pattern |
| `remedial_action` | Engine instruction: `serve_same_level`, `go_down_grade`, `go_prereq_skill`, `flag_review` |
| `remedial_skill_id` | The skill to target for the next question |
| `remedial_grade` | The grade level to pull the next question from |

**Example:** If a student picks an option tagged `Concept_Error` with `go_down_grade`, the engine traverses the Knowledge Graph and serves a question from one grade below targeting `remedial_skill_id`. If tagged `Careless_Slip` with `serve_same_level`, the student stays at the same grade and difficulty.

---

### Sheet 5 — `5_Dimensions` → DB Table: `question_dimensions`
Tags each question across 5 learning axes.

| Column | Description |
|---|---|
| `question_id` | FK → `questions` |
| `dim_reading` | `1` = requires reading comprehension |
| `dim_understanding` | `1` = tests conceptual understanding |
| `dim_application` | `1` = applies concept to a new context |
| `dim_calculation` | `1` = tests arithmetic/algebraic accuracy |
| `dim_retention` | `1` = re-tests a previously seen concept |
| `primary_dimension` | `Reading`, `Understanding`, `Application`, `Calculation`, `Retention` |
| `word_eq_pair_id` | For word problems: the `question_id` of the equation-only twin. Mirrors `equation_twin_id` in Sheet 2. Used to detect Reading vs. Math gaps. |

---

## PART 2 — THE ALGORITHM ENGINE (Detailed Logic)

Build a stateful backend algorithm engine that orchestrates all four algorithms in sequence on every question response.

---

### Algorithm 1 — CAT + IRT (Computerised Adaptive Testing with Item Response Theory)

**Purpose:** Dynamically select the right difficulty question at every step.

**IRT Model:** Use the 3-Parameter Logistic (3PL) model:
```
P(θ) = c + (1 - c) / (1 + exp(-a(θ - b)))
```
Where `θ` = estimated student ability, `b` = item difficulty, `a` = item discrimination, `c` = guessing parameter.

**Initialisation:**
- Student selects their grade level at the start (Grades 5–10).
- The engine initialises `θ` (ability) at 0.0 (midpoint of the IRT scale).
- The first question is pulled from the student's selected grade at `medium` difficulty.

**After each response, update θ using Maximum Likelihood Estimation (MLE):**
- Correct → increase `θ` (serve a harder question or advance to the next model/topic).
- Incorrect → decrease `θ` (serve an easier question in the same topic/skill before traversal).

**Difficulty progression within a topic:**
- Each topic has questions at `easy`, `medium`, and `hard` difficulty bands.
- Within the same topic, the engine must serve at least one question from each difficulty band before moving to a new topic model.
- Correct streaks (≥ 2 consecutive correct answers) → escalate difficulty band or advance to the next topic model.
- Incorrect responses → descend difficulty band within same topic first, then trigger cross-grade traversal if failures persist.

**Cross-Grade Traversal Rule:**
- If the student fails 2 consecutive questions within the same topic at `easy` difficulty → trigger Knowledge Graph traversal.
- The engine checks `prerequisite_skill_ids` for the current topic and traverses to the prerequisite skill, dropping grade level by 1 (e.g. Grade 9 → Grade 8 → Grade 7, down to Grade 5 root nodes).
- After the prerequisite gap is confirmed or cleared, return to the next topic model in the student's original grade.

---

### Algorithm 2 — CDM (Cognitive Diagnostic Model) with Q-Matrix

**Purpose:** Diagnose *why* a student got a question wrong, not just *that* they got it wrong.

**Implementation:**

When a student selects a wrong answer:
1. Look up the `answer_traps` table using `{question_id, option_label}`.
2. Retrieve: `trap_type`, `skill_gap_id`, `misconception`, `misconception_detail`, `remedial_action`, `remedial_skill_id`, `remedial_grade`.
3. Log the `trap_type` to the student's session record.
4. Execute the `remedial_action`:
   - `serve_same_level` → re-serve a different question at the same grade and difficulty (Careless Slip recovery).
   - `go_down_grade` → serve a question from `remedial_grade` targeting `remedial_skill_id` (Concept/Sign Error).
   - `go_prereq_skill` → traverse the Knowledge Graph to the prerequisite skill (deep misconception).
   - `flag_review` → mark the skill for teacher review, continue assessment.

**Trap Type Decision Matrix:**

| Trap Type | Interpretation | Engine Action |
|---|---|---|
| `Careless_Slip` | Minor arithmetic error; knows the concept | `serve_same_level` — retry at same difficulty |
| `Calculation_Error` | Mechanical execution error | `serve_same_level` with calculation-focused question |
| `Concept_Error` | Fundamental misunderstanding | `go_down_grade` to the prerequisite skill |
| `Sign_Error` | Positive/negative confusion | `go_prereq_skill` → Integer rules (Grade 6–7) |
| `Procedural_Error` | Knows concept, wrong steps | `serve_same_level` with step-by-step question |
| `Reading_Error` | Language comprehension issue | Trigger Twin Question diagnostic (see Part 2.4) |

**Q-Matrix Integration:**
- When a question tests multiple skills (multiple `1`s in Sheet 3), and the student answers wrong, the CDM uses the Q-Matrix to narrow which specific skill is deficient based on the `trap_type` and `skill_gap_id` in Sheet 4.

---

### Algorithm 3 — BKT (Bayesian Knowledge Tracing)

**Purpose:** Track the probability that the student has *truly mastered* each skill, accounting for lucky guesses and careless slips.

**BKT Parameters per skill:**
- `P(L0)` — Initial probability of mastery (prior, e.g. 0.1 for a new skill)
- `P(T)` — Probability of learning/transition per attempt (e.g. 0.3)
- `P(G)` — Probability of a lucky guess (e.g. 0.2 for 4-option MCQ = 0.25, tuned lower)
- `P(S)` — Probability of a careless slip despite mastery (e.g. 0.1)

**Update Rule after each response:**

On a **correct** answer:
```
P(L | correct) = [P(L) * (1 - P(S))] / [P(L) * (1 - P(S)) + (1 - P(L)) * P(G)]
```
Then: `P(L_new) = P(L | correct) + (1 - P(L | correct)) * P(T)`

On an **incorrect** answer:
```
P(L | incorrect) = [P(L) * P(S)] / [P(L) * P(S) + (1 - P(L)) * (1 - P(G))]
```
Then: `P(L_new) = P(L | incorrect) + (1 - P(L | incorrect)) * P(T)`

**Mastery Threshold:** If `P(L) ≥ 0.95` for a skill → mark as **Mastered** and stop testing that skill. If `P(L) ≤ 0.30` after 3 attempts → mark as **Foundational Gap** and trigger prerequisite traversal.

**Lucky Guess Detection:** If a student answers correctly but `P(L)` before the answer was < 0.2 (low mastery prior), flag the response as a probable lucky guess. Do not immediately escalate difficulty. Serve one confirmation question for the same skill before advancing.

**Careless Slip Detection:** If `trap_type = Careless_Slip` AND `P(L) ≥ 0.70`, the engine recognises this as a slip, not a gap. It does not regress grade level — it retries the same skill at the same level.

---

### Algorithm 4 — DKT (Deep Knowledge Tracing)

**Purpose:** Model long-range skill interactions. A student's performance on Fractions (S_009) should inform the engine's prior for Decimals (S_006) and Rational Numbers (S_024) since they share prerequisite chains.

**Implementation Approach (Lightweight DKT for initial build):**
- Maintain a skill interaction matrix seeded from the `prerequisite_skill_ids` in Sheet 1.
- When a student's `P(L)` for a skill is updated by BKT, propagate a partial update to all skills that list it as a prerequisite: `P(L_child) += 0.15 * delta_P(L_parent)` (tunable coefficient).
- This ensures the engine does not re-test prerequisite skills the student has already demonstrated mastery of via related questions.
- For a full production build, replace this with a trained LSTM/GRU network using historical student response sequences as input and predicting the probability of correct response for each skill at each timestep.

---

### Algorithm 5 — Twin Question Diagnostic (Word Problem vs. Equation Isolation)

**Purpose:** Determine whether a student's error on a word problem is due to a **Reading/Comprehension gap** or a **Mathematical Concept gap**.

**Trigger Condition:** A student answers a word problem (`word_problem_flag = YES`) incorrectly.

**Logic Flow:**
1. Immediately serve the `equation_twin_id` question — the same mathematical problem expressed as a pure equation, stripped of all narrative text.
2. Evaluate both responses:

| Word Problem | Equation Twin | Diagnosis | Action |
|---|---|---|---|
| Incorrect | **Correct** | **Reading/Comprehension Error** | Flag `dim_reading` gap. Do not regress grade. Notify in report: "Strong in Math, struggles with English word problems." |
| Incorrect | **Incorrect** | **Math Concept Error** | Proceed with CDM + BKT traversal. Regress to prerequisite skill. |
| Correct | N/A (no twin) | No issue | Advance difficulty as normal. |

3. Log the outcome as `Reading_Error` or `Concept_Error` in the session's CDM record.
4. The twin question should not count as a separate "model" question — it is a diagnostic probe only.

---

## PART 3 — THE ADAPTIVE FLOW ORCHESTRATION (Master Algorithm Loop)

The following pseudocode defines the **Next-Question-Selection Loop**. Implement this as a backend service function `get_next_question(student_id, session_id, last_response)`.

```
function get_next_question(student_id, session_id, last_response):

  session = load_session(student_id, session_id)
  skill_state = load_bkt_state(student_id)     # P(L) per skill
  current_θ = session.theta                    # IRT ability estimate

  if last_response is None:
    # Initialisation
    grade = session.selected_grade
    skill = get_first_topic(grade)
    return fetch_question(skill_id=skill, grade=grade, difficulty='medium')

  # Step 1 — CDM: Identify trap if wrong
  if last_response.is_correct == False:
    trap = lookup_answer_trap(last_response.question_id, last_response.selected_option)
    log_error(student_id, trap.trap_type, trap.skill_gap_id, trap.misconception)

    # Step 2 — Twin Question check for Word Problems
    if last_response.question.word_problem_flag == YES and session.twin_probe_pending == False:
      session.twin_probe_pending = True
      session.twin_origin_question = last_response.question_id
      return fetch_question(question_id=last_response.question.equation_twin_id)

    if session.twin_probe_pending == True:
      session.twin_probe_pending = False
      twin_correct = last_response.is_correct
      word_correct = False  # (we know this from the original response)
      if twin_correct == True and word_correct == False:
        log_reading_error(student_id, session.twin_origin_question)
        # Do NOT regress — just flag and continue
        next_skill = session.current_skill
        return fetch_question(skill_id=next_skill, grade=session.current_grade, difficulty=session.current_difficulty)
      # If both wrong, fall through to CDM remediation below

    # Step 3 — Execute CDM remedial action
    if trap.remedial_action == 'serve_same_level':
      return fetch_question(skill_id=session.current_skill, grade=session.current_grade, difficulty=session.current_difficulty)

    elif trap.remedial_action == 'go_down_grade':
      new_grade = max(session.current_grade - 1, 5)
      return fetch_question(skill_id=trap.remedial_skill_id, grade=new_grade, difficulty='easy')

    elif trap.remedial_action == 'go_prereq_skill':
      prereq = get_prerequisite(session.current_skill)
      return fetch_question(skill_id=prereq.skill_id, grade=prereq.grade_level, difficulty='easy')

    elif trap.remedial_action == 'flag_review':
      flag_for_teacher(student_id, session.current_skill)
      # Continue to next topic
      next_skill = get_next_topic(session)
      return fetch_question(skill_id=next_skill, grade=session.current_grade, difficulty='medium')

  # Step 4 — BKT Update (runs on every response)
  updated_P_L = bkt_update(
    prior=skill_state[session.current_skill],
    is_correct=last_response.is_correct,
    trap_type=trap.trap_type if not last_response.is_correct else None
  )
  save_bkt_state(student_id, session.current_skill, updated_P_L)
  propagate_dkt(student_id, session.current_skill, updated_P_L)

  # Step 5 — IRT θ Update
  current_θ = irt_update_theta(current_θ, last_response)
  session.theta = current_θ

  # Step 6 — Mastery Check
  if updated_P_L >= 0.95:
    # Mastered — advance to next topic
    next_skill = get_next_topic(session)
    return fetch_question(skill_id=next_skill, grade=session.current_grade, difficulty='medium')

  if updated_P_L <= 0.30 and session.consecutive_failures >= 2:
    # Foundational gap — traverse prerequisite
    prereq = get_prerequisite(session.current_skill)
    return fetch_question(skill_id=prereq.skill_id, grade=prereq.grade_level, difficulty='easy')

  # Step 7 — Lucky Guess Guard
  if last_response.is_correct and skill_state[session.current_skill] < 0.20:
    session.pending_confirmation = True
    return fetch_question(skill_id=session.current_skill, grade=session.current_grade, difficulty=session.current_difficulty)

  # Step 8 — Standard Progression
  if last_response.is_correct:
    new_difficulty = escalate_difficulty(session.current_difficulty)
    return fetch_question(skill_id=session.current_skill, grade=session.current_grade, difficulty=new_difficulty)
  else:
    new_difficulty = reduce_difficulty(session.current_difficulty)
    return fetch_question(skill_id=session.current_skill, grade=session.current_grade, difficulty=new_difficulty)
```

---

## PART 4 — DATABASE SCHEMA

Design a PostgreSQL (or equivalent relational) database. Below is the required schema.

```sql
-- Sheet 1
CREATE TABLE skills (
  skill_id VARCHAR(10) PRIMARY KEY,
  skill_name VARCHAR(100) NOT NULL,
  grade_level VARCHAR(10),
  topic_area VARCHAR(50),
  difficulty_band VARCHAR(10),
  prerequisite_skill_ids TEXT,  -- comma-separated; parse into knowledge_graph on import
  notes TEXT
);

-- Knowledge Graph (parsed from prerequisite_skill_ids)
CREATE TABLE knowledge_graph (
  child_skill_id VARCHAR(10) REFERENCES skills(skill_id),
  parent_skill_id VARCHAR(10) REFERENCES skills(skill_id),
  PRIMARY KEY (child_skill_id, parent_skill_id)
);

-- Sheet 2
CREATE TABLE questions (
  question_id VARCHAR(50) PRIMARY KEY,
  question_text TEXT NOT NULL,
  question_type VARCHAR(20),
  word_problem_flag BOOLEAN DEFAULT FALSE,
  equation_twin_id VARCHAR(50) REFERENCES questions(question_id),
  primary_skill_id VARCHAR(10) REFERENCES skills(skill_id),
  secondary_skill_ids TEXT,
  grade_level INTEGER,
  difficulty_band VARCHAR(10),
  option_a TEXT, option_b TEXT, option_c TEXT, option_d TEXT,
  correct_option CHAR(1)
);

-- Sheet 3
CREATE TABLE q_matrix (
  question_id VARCHAR(50) REFERENCES questions(question_id),
  skill_id VARCHAR(10) REFERENCES skills(skill_id),
  PRIMARY KEY (question_id, skill_id)
);

-- Sheet 4
CREATE TABLE answer_traps (
  id SERIAL PRIMARY KEY,
  question_id VARCHAR(50) REFERENCES questions(question_id),
  option_label CHAR(1),
  option_text TEXT,
  trap_type VARCHAR(30),
  skill_gap_id VARCHAR(10) REFERENCES skills(skill_id),
  misconception VARCHAR(100),
  misconception_detail TEXT,
  remedial_action VARCHAR(30),
  remedial_skill_id VARCHAR(10) REFERENCES skills(skill_id),
  remedial_grade INTEGER
);

-- Sheet 5
CREATE TABLE question_dimensions (
  question_id VARCHAR(50) PRIMARY KEY REFERENCES questions(question_id),
  dim_reading BOOLEAN,
  dim_understanding BOOLEAN,
  dim_application BOOLEAN,
  dim_calculation BOOLEAN,
  dim_retention BOOLEAN,
  primary_dimension VARCHAR(20),
  word_eq_pair_id VARCHAR(50)
);

-- Students
CREATE TABLE students (
  student_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(100),
  email VARCHAR(100) UNIQUE,
  school VARCHAR(100),
  class_grade INTEGER,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Assessment Sessions
CREATE TABLE sessions (
  session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  student_id UUID REFERENCES students(student_id),
  selected_grade INTEGER,
  current_theta FLOAT DEFAULT 0.0,
  current_skill_id VARCHAR(10),
  current_grade INTEGER,
  current_difficulty VARCHAR(10),
  consecutive_failures INTEGER DEFAULT 0,
  status VARCHAR(20) DEFAULT 'in_progress',
  started_at TIMESTAMP DEFAULT NOW(),
  ended_at TIMESTAMP
);

-- Responses
CREATE TABLE responses (
  response_id SERIAL PRIMARY KEY,
  session_id UUID REFERENCES sessions(session_id),
  question_id VARCHAR(50) REFERENCES questions(question_id),
  selected_option CHAR(1),
  is_correct BOOLEAN,
  trap_type VARCHAR(30),
  skill_gap_id VARCHAR(10),
  misconception VARCHAR(100),
  twin_probe BOOLEAN DEFAULT FALSE,
  response_time_ms INTEGER,
  responded_at TIMESTAMP DEFAULT NOW()
);

-- BKT State (per student per skill)
CREATE TABLE bkt_state (
  student_id UUID REFERENCES students(student_id),
  skill_id VARCHAR(10) REFERENCES skills(skill_id),
  p_mastery FLOAT DEFAULT 0.10,
  attempts INTEGER DEFAULT 0,
  last_updated TIMESTAMP,
  PRIMARY KEY (student_id, skill_id)
);

-- Dimension Scores (aggregated per session)
CREATE TABLE dimension_scores (
  session_id UUID REFERENCES sessions(session_id),
  dim_reading FLOAT,
  dim_understanding FLOAT,
  dim_application FLOAT,
  dim_calculation FLOAT,
  dim_retention FLOAT,
  PRIMARY KEY (session_id)
);
```

---

## PART 5 — USER INTERFACES

### 5.1 Student Assessment Interface

**Design Principles:** Clean, distraction-free, mobile-responsive. No clutter. One question at a time.

**Screens to Build:**
1. **Landing / Grade Selection Screen:** Student enters name, school, and selects their class (Grade 5–10). Clean card-based UI.
2. **Assessment Screen:**
   - Displays one question at a time with four MCQ options.
   - Shows current topic/skill name and a non-intrusive progress indicator (not a percentage — use a skill breadcrumb like "Topic: Algebra → Linear Equations").
   - Subtle timer per question (optional, configurable by admin).
   - No feedback on right/wrong during assessment — to avoid coaching the next response.
3. **Assessment Complete Screen:** Simple transition to the report.
4. **Post-Assessment Report (Student View):**
   - **Hero Section:** Overall score and grade-equivalent level (e.g. "You are performing at a Grade 7 level in Algebra").
   - **5-Dimension Radar Chart:** Visual spider/radar chart plotting percentage scores across Reading, Understanding, Application, Calculation, and Retention.
   - **Skill Breakdown Table:** Per-skill mastery probability (from BKT) shown as a progress bar. Colour-coded: Green (Mastered), Yellow (Developing), Red (Gap).
   - **Root Cause Diagnosis Card:** Plain-English summary written by the diagnostic engine. Examples:
     - *"You have strong calculation skills (82%) but struggle to decode word problems (34%). This is a reading comprehension gap, not a math gap."*
     - *"Your Algebra errors are rooted in a weak understanding of Integer rules (Grade 7). Strengthening integers will unlock Linear Equations."*
   - **Foundational Gaps Section:** Lists the deepest prerequisite gaps identified during traversal, with the specific grade level and skill name.
   - **Recommended Focus Areas:** Top 3 skills to study next, with NCERT chapter references.

---

### 5.2 Admin / Teacher Dashboard

**Authentication:** Separate admin login with role-based access (Admin, Teacher, Viewer).

**Screens to Build:**

1. **Dashboard Home:**
   - Total students assessed, assessments this week, average score by grade.
   - Class-level heatmap: Which skills have the highest failure rates across all students.

2. **Student List & Search:**
   - Table of all students with columns: Name, Grade, Last Assessment Date, Overall Score, Status.
   - Click into any student to see their full diagnostic report (same as the student report view, plus raw response logs).

3. **Cohort Analytics:**
   - Grade-level performance trends over time.
   - Bar chart: Most common `trap_type` errors across the cohort (e.g. "68% of Grade 8 students are making Concept_Errors on Factorisation").
   - Prerequisite gap tracker: Which foundational skills (e.g. "Grade 6 Integers") are blocking the most higher-grade students.

4. **Question Bank Manager:**
   - **Excel Import Panel:** Upload a 5-sheet Excel workbook. On upload:
     - Parse all 5 sheets.
     - Validate: Check for missing required fields (pink columns), invalid FK references, missing equation twins.
     - Show a preview diff of new vs. existing records.
     - Confirm → bulk insert into database.
   - Browse, filter, and search the existing question bank by grade, skill, difficulty, word_problem_flag.
   - Manually add/edit/delete individual questions (with form validation matching the Excel schema).

5. **Session Replay (Optional but valuable):**
   - View a full timeline of any student's assessment session: each question served, the option selected, the `trap_type` fired, and the engine's next-question decision. Useful for validating algorithm behaviour.

---

## PART 6 — TECH STACK RECOMMENDATION

| Layer | Technology | Reason |
|---|---|---|
| **Frontend** | React + Next.js (App Router) | SSR for fast report loading; component model suits dashboards |
| **Styling** | Tailwind CSS + shadcn/ui | Rapid, consistent design with accessible components |
| **Charts** | Recharts or Chart.js | Radar charts, bar charts, progress indicators for reports |
| **Backend / API** | Node.js with Express or Next.js API Routes | Tight integration with frontend; fast JSON APIs |
| **Algorithm Engine** | Python (FastAPI microservice) | NumPy/SciPy for IRT MLE; cleaner for BKT/DKT numerical methods |
| **Database** | PostgreSQL | Relational integrity for the 5-table schema; complex joins for cohort queries |
| **ORM** | Prisma (Node) or SQLAlchemy (Python) | Type-safe schema management |
| **Excel Parsing** | `xlsx` (Node.js) or `openpyxl` / `pandas` (Python) | Parse the 5-sheet workbook on admin import |
| **Auth** | NextAuth.js or Clerk | Student sessions + admin RBAC |
| **Deployment** | Vercel (frontend) + Railway or Render (backend + DB) | Simple, scalable |

**API Contract between Frontend and Algorithm Engine:**
- `POST /api/session/start` → `{ student_id, selected_grade }` → returns first question
- `POST /api/session/respond` → `{ session_id, question_id, selected_option }` → returns next question + updated BKT state
- `GET /api/session/report/:session_id` → returns full diagnostic report object
- `POST /api/admin/import` → multipart Excel upload → returns validation report + import summary

---

## PART 7 — VALIDATION & EDGE CASE REQUIREMENTS

Build explicit handling for:

1. **No available questions:** If the engine tries to fetch a question for a given `{skill_id, grade, difficulty}` and none exist, fall back to the nearest available difficulty band, then to the nearest available grade.
2. **Session termination conditions:** End the session after: (a) all topic models for the selected grade have been visited, OR (b) a configurable max question count (e.g. 30 questions) is reached, OR (c) mastery is confirmed (`P(L) ≥ 0.95`) for all skills at the selected grade.
3. **Repeated question prevention:** Never serve the same `question_id` twice in a session.
4. **Twin question integrity:** If a word problem has no `equation_twin_id`, skip the twin diagnostic and proceed directly with CDM.
5. **Grade floor/ceiling:** Grade traversal cannot go below Grade 5 or above Grade 10.
6. **Incomplete Excel import:** If any required sheet is missing or required columns are empty, reject the import and return a detailed validation error report listing every row and column with issues.

---

## PART 8 — REPORT GENERATION LOGIC

The report engine must aggregate the following after session end:

1. **Skill Mastery Map:** Final `P(L)` from `bkt_state` for every skill encountered in the session.
2. **Error Taxonomy Summary:** Count of each `trap_type` across all responses → convert to percentages.
3. **Dimension Scores:** For each of the 5 dimensions, calculate:
   `score = (correct responses where dim_X = 1) / (total questions where dim_X = 1) * 100`
4. **Grade-Equivalent Level:** The highest grade at which the student demonstrated consistent mastery (≥ 70% correct, ≥ 3 questions).
5. **Reading vs. Math Gap Diagnosis:** Count of `Reading_Error` flags vs. `Concept_Error` flags. If Reading_Error > 30% of word problem failures → generate reading gap narrative.
6. **Foundational Gap Chain:** List every prerequisite traversal that occurred during the session (the full chain: e.g. "Grade 9 Linear Equations → Grade 8 Basic Algebra → Grade 7 Integers"). This is the root cause chain shown in the report.
7. **Personalised Narrative:** Use templated logic to generate 3–5 plain-English sentences summarising the student's performance profile, their primary error type, and their root foundational gap.

---

## SUMMARY OF DELIVERABLES

Build and deliver the following:

1. ✅ Complete PostgreSQL schema (all 9 tables above with indexes and FKs)
2. ✅ Excel import parser (validates and ingests all 5 sheets)
3. ✅ Algorithm engine: CAT/IRT + CDM (Q-Matrix + Answer Traps) + BKT + DKT + Twin Question logic
4. ✅ Next-question-selection API endpoint with full orchestration loop
5. ✅ Student-facing assessment UI (Grade selection → Question flow → Diagnostic report)
6. ✅ Admin dashboard (Student management, Cohort analytics, Question bank import)
7. ✅ Post-assessment report with 5-dimension radar chart, skill mastery bars, root cause narrative, and foundational gap chain
8. ✅ Edge case and validation handling throughout

---

*Reference files: `Adaptive_Math_SME_Template_v3_FILLED.xlsx` (5-sheet question bank with 235+ sample questions across Grades 5–10), `Adaptive_Math_Assessment_Tool.pptx` (algorithm walkthroughs and CDM examples). Build everything to be compatible with this exact data format.*
