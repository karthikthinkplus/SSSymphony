import axios from 'axios'

const API_BASE = '/api'

const api = axios.create({ baseURL: API_BASE })

// Inject admin JWT from localStorage
api.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('admin_token')
    if (token) config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// ── Session (Student) ──────────────────────────────────────────────────────
export interface SessionStartRequest { name: string; school: string; grade: number }
export interface QuestionOut {
  question_id: string
  question_text: string
  question_type: string
  word_problem_flag: boolean
  grade_level: number
  difficulty_band: string
  skill_name: string
  topic_area: string
  option_a: string
  option_b: string
  option_c: string
  option_d: string
  question_number: number
  is_twin_probe: boolean
}
export interface SessionStartResponse {
  session_id: string
  student_id: string
  first_question: QuestionOut
}
export interface RespondResponse {
  is_correct: boolean
  session_complete: boolean
  next_question: QuestionOut | null
  bkt_update: Record<string, number> | null
  engine_action: string | null
}
export interface SkillMastery {
  skill_id: string
  skill_name: string
  grade_level: string
  topic_area: string
  p_mastery: number
  attempts: number
  status: string
}
export interface ReportData {
  session_id: string
  student_name: string
  school: string
  selected_grade: number
  grade_equivalent_level: number
  total_questions: number
  correct_answers: number
  accuracy_pct: number
  dimension_scores: { reading: number; understanding: number; application: number; calculation: number; retention: number }
  skill_mastery: SkillMastery[]
  error_taxonomy: Record<string, number>
  reading_gap_detected: boolean
  reading_gap_pct: number
  foundational_gap_chain: Array<{ from_skill: string; from_grade: number; to_skill: string; to_grade: number; reason: string }>
  narrative: string
  recommended_skills: Array<{ skill_id: string; skill_name: string; grade_level: string; ncert_ref: string }>
  started_at: string
  ended_at: string | null
}

export const sessionApi = {
  start: (data: SessionStartRequest) =>
    api.post<SessionStartResponse>('/session/start', data).then(r => r.data),
  respond: (data: { session_id: string; question_id: string; selected_option: string; response_time_ms?: number }) =>
    api.post<RespondResponse>('/session/respond', data).then(r => r.data),
  getReport: (session_id: string) =>
    api.get<ReportData>(`/session/report/${session_id}`).then(r => r.data),
  getStatus: (session_id: string) =>
    api.get(`/session/${session_id}/status`).then(r => r.data),
}

// ── Admin ──────────────────────────────────────────────────────────────────
export const adminApi = {
  login: (username: string, password: string) =>
    api.post('/admin/login', { username, password }).then(r => r.data),
  getDashboard: () => api.get('/admin/dashboard').then(r => r.data),
  getStudents: (params?: { search?: string; grade?: number; skip?: number; limit?: number }) =>
    api.get('/admin/students', { params }).then(r => r.data),
  getStudentReport: (student_id: string) =>
    api.get(`/admin/student/${student_id}/report`).then(r => r.data),
  getCohort: (grade: number) =>
    api.get(`/admin/cohort/${grade}`).then(r => r.data),
  getSessionReplay: (session_id: string) =>
    api.get(`/admin/session/${session_id}/replay`).then(r => r.data),
  getQuestions: (params?: { grade?: number; difficulty?: string; skill_id?: string; word_problem?: boolean; search?: string; skip?: number; limit?: number }) =>
    api.get('/admin/questions', { params }).then(r => r.data),
  importExcel: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/admin/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(r => r.data)
  },
}

export default api
