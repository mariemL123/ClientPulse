
const API_BASE_URL = (import.meta.env.VITE_API_URL?.trim() || 'http://127.0.0.1:8000').replace(/\/+$/, '')

const TOKEN_KEY = 'clientpulse_access_token'

// ============================================================
// TYPES : UTILISATEURS
// ============================================================

export type User = {
  id: number
  full_name: string
  email: string
  role: 'admin' | 'agent'
  is_active: boolean
  created_at: string
}

export type UserCreate = {
  full_name: string
  email: string
  password: string
}

export type UserUpdate = {
  full_name?: string
  email?: string
}

export type UserStatusUpdate = {
  is_active: boolean
}

// Informations complÃ©mentaires en cas de suppression nÃ©cessitant
// une rÃ©affectation des tickets.
export type UserDeleteConflict = {
  message: string
  ticket_count: number
  requires_replacement: boolean
}

// ============================================================
// TYPES : CLIENTS
// ============================================================

export type Client = {
  id: number
  name: string
  email: string
  company: string | null
  phone: string | null
  status: 'active' | 'inactive' | 'prospect'
}

export type ClientCreate = {
  name: string
  email: string
  company?: string | null
  phone?: string | null
  status: 'active' | 'inactive' | 'prospect'
}

export type ClientUpdate = Partial<ClientCreate>

// ============================================================
// TYPES : TICKETS
// ============================================================

export type Ticket = {
  id: number
  title: string
  description: string
  priority: 'low' | 'medium' | 'high' | 'urgent'
  status: 'open' | 'in_progress' | 'resolved' | 'closed'
  client_id: number
  assigned_to: string | null
  created_at: string
  updated_at: string
  resolved_at: string | null
}

export type TicketCreate = {
  title: string
  description: string
  priority: 'low' | 'medium' | 'high' | 'urgent'
  status: 'open' | 'in_progress' | 'resolved' | 'closed'
  client_id: number
  assigned_to?: string | null
}

export type TicketUpdate = Partial<TicketCreate>

// ============================================================
// TYPES : TABLEAU DE BORD
// ============================================================

export type DashboardStatistics = {
  clients: {
    total: number
    active: number
    inactive: number
    prospect: number
  }
  tickets: {
    total: number
    open: number
    in_progress: number
    resolved: number
    closed: number
  }
  priorities: {
    low: number
    medium: number
    high: number
    urgent: number
  }
  resolution_rate: number
}

type LoginResponse = {
  access_token: string
  token_type: string
}

// ============================================================
// GESTION CENTRALISEE DES ERREURS API
// ============================================================

export class ApiError extends Error {
  public readonly status: number
  public readonly detail: unknown

  constructor(
    message: string,
    status: number,
    detail: unknown = null,
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

// ============================================================
// AUTHENTIFICATION ET TOKEN JWT
// ============================================================

function getToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY)
}

export async function login(
  email: string,
  password: string,
): Promise<User> {
  const result = await request<LoginResponse>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })

  sessionStorage.setItem(TOKEN_KEY, result.access_token)

  try {
    return await getCurrentUser()
  } catch (error) {
    sessionStorage.removeItem(TOKEN_KEY)
    throw error
  }
}

export async function getCurrentUser(): Promise<User> {
  return request<User>('/api/auth/me')
}

export function logout(): void {
  sessionStorage.removeItem(TOKEN_KEY)
}

// ============================================================
// FONCTION GENERIQUE POUR LES REQUETES HTTP
// ============================================================

async function request<T>(
  endpoint: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers)

  if (options.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  const token = getToken()

  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  let response: Response

  try {
    response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers,
    })
  } catch {
    throw new ApiError(
      'Impossible de joindre le serveur ClientPulse.',
      0,
    )
  }

  if (!response.ok) {
    // Une session authentifi?e n'est plus valide : pr?venir l'application.
    // Ne pas d?clencher cet ?v?nement pour une erreur de connexion.
    if (response.status === 401 && token && endpoint !== '/api/auth/login') {
      logout()
      window.dispatchEvent(new Event('clientpulse:unauthorized'))
    }

    let message = `Erreur HTTP ${response.status}`
    let detail: unknown = null

    try {
      const data: unknown = await response.json()

      if (
        typeof data === 'object' &&
        data !== null &&
        'detail' in data
      ) {
        detail = data.detail

        if (typeof data.detail === 'string') {
          message = data.detail
        } else if (Array.isArray(data.detail)) {
          message = data.detail
            .map((item) => {
              if (
                typeof item === 'object' &&
                item !== null &&
                'msg' in item &&
                typeof item.msg === 'string'
              ) {
                return item.msg
              }

              return 'DonnÃ©es invalides.'
            })
            .join(' ')
        } else if (
          typeof data.detail === 'object' &&
          data.detail !== null &&
          'message' in data.detail &&
          typeof data.detail.message === 'string'
        ) {
          message = data.detail.message
        }
      }
    } catch {
      // Certaines rÃ©ponses HTTP ne contiennent pas de JSON.
    }

    throw new ApiError(message, response.status, detail)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}

// ============================================================
// TABLEAU DE BORD
// ============================================================

export async function getDashboard(): Promise<DashboardStatistics> {
  return request<DashboardStatistics>('/api/dashboard')
}

// ============================================================
// UTILISATEURS - ADMINISTRATION
// ============================================================

export async function getUsers(): Promise<User[]> {
  return request<User[]>('/api/users/')
}

export async function getUser(userId: number): Promise<User> {
  if (!Number.isInteger(userId) || userId <= 0) {
    throw new ApiError('Identifiant utilisateur invalide.', 400)
  }

  return request<User>(`/api/users/${userId}`)
}

export async function createUser(
  user: UserCreate,
): Promise<User> {
  return request<User>('/api/users/', {
    method: 'POST',
    body: JSON.stringify(user),
  })
}

export async function updateUser(
  userId: number,
  changes: UserUpdate,
): Promise<User> {
  if (!Number.isInteger(userId) || userId <= 0) {
    throw new ApiError('Identifiant utilisateur invalide.', 400)
  }

  if (Object.keys(changes).length === 0) {
    throw new ApiError('Aucune modification Ã  enregistrer.', 400)
  }

  return request<User>(`/api/users/${userId}`, {
    method: 'PATCH',
    body: JSON.stringify(changes),
  })
}

export async function updateUserStatus(
  userId: number,
  isActive: boolean,
): Promise<User> {
  if (!Number.isInteger(userId) || userId <= 0) {
    throw new ApiError('Identifiant utilisateur invalide.', 400)
  }

  return request<User>(`/api/users/${userId}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ is_active: isActive }),
  })
}

export async function deleteUser(
  userId: number,
  replacementUserId?: number,
): Promise<void> {
  if (!Number.isInteger(userId) || userId <= 0) {
    throw new ApiError('Identifiant utilisateur invalide.', 400)
  }

  const params = new URLSearchParams()

  if (replacementUserId !== undefined) {
    if (
      !Number.isInteger(replacementUserId) ||
      replacementUserId <= 0 ||
      replacementUserId === userId
    ) {
      throw new ApiError('Agent de remplacement invalide.', 400)
    }

    params.set('replacement_user_id', String(replacementUserId))
  }

  const query = params.toString()
  const endpoint = `/api/users/${userId}${query ? `?${query}` : ''}`

  return request<void>(endpoint, {
    method: 'DELETE',
  })
}

// ============================================================
// CLIENTS
// ============================================================

export async function getClients(
  skip = 0,
  limit = 20,
): Promise<Client[]> {
  const params = new URLSearchParams({
    skip: String(skip),
    limit: String(limit),
  })

  return request<Client[]>(`/api/clients?${params.toString()}`)
}

export async function getClient(clientId: number): Promise<Client> {
  if (!Number.isInteger(clientId) || clientId <= 0) {
    throw new ApiError('Identifiant client invalide.', 400)
  }

  return request<Client>(`/api/clients/${clientId}`)
}

export async function createClient(
  client: ClientCreate,
): Promise<Client> {
  return request<Client>('/api/clients', {
    method: 'POST',
    body: JSON.stringify(client),
  })
}

export async function updateClient(
  clientId: number,
  changes: ClientUpdate,
): Promise<Client> {
  if (!Number.isInteger(clientId) || clientId <= 0) {
    throw new ApiError('Identifiant client invalide.', 400)
  }

  if (Object.keys(changes).length === 0) {
    throw new ApiError('Aucune modification Ã  enregistrer.', 400)
  }

  return request<Client>(`/api/clients/${clientId}`, {
    method: 'PATCH',
    body: JSON.stringify(changes),
  })
}

export async function deleteClient(
  clientId: number,
): Promise<void> {
  if (!Number.isInteger(clientId) || clientId <= 0) {
    throw new ApiError('Identifiant client invalide.', 400)
  }

  return request<void>(`/api/clients/${clientId}`, {
    method: 'DELETE',
  })
}

// ============================================================
// TICKETS
// ============================================================

export async function getTickets(
  skip = 0,
  limit = 20,
): Promise<Ticket[]> {
  const params = new URLSearchParams({
    skip: String(skip),
    limit: String(limit),
  })

  return request<Ticket[]>(`/api/tickets?${params.toString()}`)
}

export async function getTicket(
  ticketId: number,
): Promise<Ticket> {
  if (!Number.isInteger(ticketId) || ticketId <= 0) {
    throw new ApiError('Identifiant ticket invalide.', 400)
  }

  return request<Ticket>(`/api/tickets/${ticketId}`)
}

export async function createTicket(
  ticket: TicketCreate,
): Promise<Ticket> {
  return request<Ticket>('/api/tickets', {
    method: 'POST',
    body: JSON.stringify(ticket),
  })
}

export async function updateTicket(
  ticketId: number,
  changes: TicketUpdate,
): Promise<Ticket> {
  if (!Number.isInteger(ticketId) || ticketId <= 0) {
    throw new ApiError('Identifiant ticket invalide.', 400)
  }

  if (Object.keys(changes).length === 0) {
    throw new ApiError('Aucune modification Ã  enregistrer.', 400)
  }

  return request<Ticket>(`/api/tickets/${ticketId}`, {
    method: 'PATCH',
    body: JSON.stringify(changes),
  })
}

export async function deleteTicket(
  ticketId: number,
): Promise<void> {
  if (!Number.isInteger(ticketId) || ticketId <= 0) {
    throw new ApiError('Identifiant ticket invalide.', 400)
  }

  return request<void>(`/api/tickets/${ticketId}`, {
    method: 'DELETE',
  })
}
