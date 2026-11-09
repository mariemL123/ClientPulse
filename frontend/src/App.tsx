import { lazy, Suspense, useEffect, useMemo, useState, type FormEvent } from 'react'
import {
  Activity, ArrowDownRight, ArrowUpRight, Bell, CalendarDays,
  ChevronDown, ClipboardList, LayoutDashboard, LogOut, Menu,
  MessageSquare, Plus, Search, ShieldCheck, Users, X, Pencil,
  Trash2, RefreshCw,
} from 'lucide-react'
import {
  ApiError,
  createClient, updateClient, deleteClient, getClients,
  getCurrentUser, getDashboard, getTickets, createTicket,
  updateTicket, deleteTicket, login, logout, getUsers,
  createUser, updateUserStatus, updateUser, deleteUser,
  type Client, type ClientCreate, type ClientUpdate,
  type DashboardStatistics, type Ticket, type TicketCreate,
  type TicketUpdate, type User, type UserCreate, type UserUpdate,
} from './services/api'

// ============================================================
// CONSTANTES ET TYPES
// ============================================================

const DashboardCharts = lazy(() => import('./DashboardCharts'))

type Page = 'Vue générale' | 'Clients' | 'Tickets' | 'Utilisateurs'

type DeleteConflict = {
  ticket_count: number
  requires_replacement: boolean
}

const navigation: { label: Page; icon: typeof LayoutDashboard; adminOnly?: boolean }[] = [
  { label: 'Vue générale', icon: LayoutDashboard },
  { label: 'Clients', icon: Users },
  { label: 'Tickets', icon: ClipboardList },
  { label: 'Utilisateurs', icon: ShieldCheck, adminOnly: true },
]

const emptyDashboard: DashboardStatistics = {
  clients: { total: 0, active: 0, inactive: 0, prospect: 0 },
  tickets: { total: 0, open: 0, in_progress: 0, resolved: 0, closed: 0 },
  priorities: { low: 0, medium: 0, high: 0, urgent: 0 },
  resolution_rate: 0,
}

const inputClass =
  'w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-100 disabled:bg-slate-100 disabled:text-slate-400'

const primaryButton =
  'inline-flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50'

const secondaryButton =
  'inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-600 transition hover:bg-slate-50 disabled:opacity-50'

const dangerButton =
  'inline-flex items-center justify-center gap-2 rounded-xl bg-red-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50'

function initials(name: string): string {
  return name.trim().split(/\s+/).slice(0, 2)
    .map((part) => part[0] ?? '').join('').toUpperCase() || 'CL'
}

function formatDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Date inconnue'

  return new Intl.DateTimeFormat('fr-FR', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  }).format(date)
}

function statusLabel(status: Ticket['status']): string {
  const labels: Record<Ticket['status'], string> = {
    open: 'Ouvert',
    in_progress: 'En cours',
    resolved: 'Résolu',
    closed: 'Fermé',
  }
  return labels[status]
}

function priorityLabel(priority: Ticket['priority']): string {
  const labels: Record<Ticket['priority'], string> = {
    low: 'Basse',
    medium: 'Moyenne',
    high: 'Haute',
    urgent: 'Urgente',
  }
  return labels[priority]
}

function statusColor(status: string): string {
  if (status === 'Ouvert') return 'bg-blue-50 text-blue-600'
  if (status === 'En cours') return 'bg-amber-50 text-amber-600'
  if (status === 'Résolu' || status === 'Fermé') return 'bg-emerald-50 text-emerald-600'
  return 'bg-slate-100 text-slate-600'
}

function priorityColor(priority: string): string {
  if (priority === 'Urgente') return 'bg-red-50 text-red-600'
  if (priority === 'Haute') return 'bg-orange-50 text-orange-600'
  if (priority === 'Moyenne') return 'bg-amber-50 text-amber-600'
  return 'bg-slate-100 text-slate-600'
}

// ============================================================
// EXTRACTION SÉCURISÉE DES INFORMATIONS D'ERREUR API
// ============================================================

function getDeleteConflict(error: unknown): DeleteConflict | null {
  if (!(error instanceof ApiError) || error.status !== 409) return null

  const detail = error.detail

  if (!detail || typeof detail !== 'object') return null

  const data = detail as Record<string, unknown>

  if (data.requires_replacement !== true) return null

  const count = Number(data.ticket_count)

  if (!Number.isInteger(count) || count < 0) return null

  return {
    ticket_count: count,
    requires_replacement: true,
  }
}

// ============================================================
// MODALE GÉNÉRIQUE
// ============================================================

function Modal({
  title,
  children,
  onClose,
}: {
  title: string
  children: React.ReactNode
  onClose: () => void
}) {
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-900/50 p-4">
      <section className="max-h-[90vh] w-full max-w-xl overflow-y-auto rounded-2xl bg-white shadow-2xl">
        <div className="sticky top-0 flex items-center justify-between border-b border-slate-100 bg-white px-6 py-4">
          <h2 className="text-lg font-bold text-slate-900">{title}</h2>
          <button
            onClick={onClose}
            className="rounded-lg p-2 text-slate-400 hover:bg-slate-100"
            aria-label="Fermer"
          >
            <X size={20} />
          </button>
        </div>
        <div className="p-6">{children}</div>
      </section>
    </div>
  )
}

// ============================================================
// CONNEXION
// ============================================================

function LoginScreen({
  onLogin,
}: {
  onLogin: (email: string, password: string) => Promise<void>
}) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setLoading(true)

    try {
      await onLogin(email.trim(), password)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Échec de la connexion.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-10">
      <section className="w-full max-w-md rounded-3xl border border-slate-200 bg-white p-8 shadow-xl">
        <div className="mb-8 flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-600 text-white">
            <Activity size={26} />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">
              Client<span className="text-blue-600">Pulse</span>
            </h1>
            <p className="text-sm text-slate-400">Customer management</p>
          </div>
        </div>

        <h2 className="text-xl font-bold text-slate-900">Bienvenue</h2>
        <p className="mt-1 text-sm text-slate-500">Connectez-vous à votre espace de travail.</p>

        <form onSubmit={handleSubmit} className="mt-7 space-y-5">
          <div>
            <label htmlFor="email" className="mb-2 block text-sm font-medium text-slate-700">
              Adresse e-mail
            </label>
            <input
              id="email"
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={inputClass}
              placeholder="nom@entreprise.com"
            />
          </div>

          <div>
            <label htmlFor="password" className="mb-2 block text-sm font-medium text-slate-700">
              Mot de passe
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={inputClass}
              placeholder="Votre mot de passe"
            />
          </div>

          {error && <p role="alert" className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-600">{error}</p>}

          <button type="submit" disabled={loading} className={`${primaryButton} w-full py-3`}>
            {loading ? 'Connexion...' : 'Se connecter'}
          </button>
        </form>

        <p className="mt-6 text-center text-xs text-slate-400">
          Accès sécurisé à votre espace ClientPulse
        </p>
      </section>
    </main>
  )
}

// ============================================================
// FORMULAIRE CLIENT
// ============================================================

function ClientForm({
  client,
  onClose,
  onSave,
}: {
  client?: Client | null
  onClose: () => void
  onSave: (data: ClientCreate | ClientUpdate) => Promise<void>
}) {
  const [name, setName] = useState(client?.name ?? '')
  const [email, setEmail] = useState(client?.email ?? '')
  const [company, setCompany] = useState(client?.company ?? '')
  const [phone, setPhone] = useState(client?.phone ?? '')
  const [status, setStatus] = useState<Client['status']>(client?.status ?? 'active')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setLoading(true)

    try {
      await onSave({
        name: name.trim(),
        email: email.trim(),
        company: company.trim() || null,
        phone: phone.trim() || null,
        status,
      })
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Impossible d’enregistrer le client.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal title={client ? 'Modifier le client' : 'Nouveau client'} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <div>
          <label className="mb-1 block text-sm font-medium">Nom complet *</label>
          <input className={inputClass} required value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">Adresse e-mail *</label>
          <input className={inputClass} type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">Entreprise</label>
          <input className={inputClass} value={company} onChange={(e) => setCompany(e.target.value)} />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">Téléphone</label>
          <input className={inputClass} value={phone} onChange={(e) => setPhone(e.target.value)} />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">Statut</label>
          <select className={inputClass} value={status} onChange={(e) => setStatus(e.target.value as Client['status'])}>
            <option value="active">Actif</option>
            <option value="inactive">Inactif</option>
            <option value="prospect">Prospect</option>
          </select>
        </div>

        {error && <p role="alert" className="text-sm text-red-600">{error}</p>}

        <div className="flex justify-end gap-3 pt-3">
          <button type="button" onClick={onClose} disabled={loading} className={secondaryButton}>Annuler</button>
          <button type="submit" disabled={loading} className={primaryButton}>
            {loading ? 'Enregistrement...' : 'Enregistrer'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

// ============================================================
// FORMULAIRE DE CRÉATION D'UTILISATEUR
// ============================================================

function UserForm({
  onClose,
  onSave,
}: {
  onClose: () => void
  onSave: (data: UserCreate) => Promise<void>
}) {
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setLoading(true)

    try {
      await onSave({ full_name: fullName.trim(), email: email.trim(), password })
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Impossible de créer le compte.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal title="Créer un compte agent" onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <div>
          <label className="mb-1 block text-sm font-medium">Nom complet *</label>
          <input className={inputClass} required minLength={2} value={fullName} onChange={(e) => setFullName(e.target.value)} />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">Adresse e-mail *</label>
          <input className={inputClass} type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">Mot de passe *</label>
          <input className={inputClass} type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} />
          <p className="mt-1 text-xs text-slate-400">Minimum 8 caractères.</p>
        </div>

        {error && <p role="alert" className="text-sm text-red-600">{error}</p>}

        <div className="flex justify-end gap-3 pt-3">
          <button type="button" onClick={onClose} disabled={loading} className={secondaryButton}>Annuler</button>
          <button type="submit" disabled={loading} className={primaryButton}>
            {loading ? 'Création...' : 'Créer le compte'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

// ============================================================
// FORMULAIRE DE MODIFICATION D'UTILISATEUR
// Le rôle n'est volontairement pas modifiable.
// ============================================================

function EditUserForm({
  target,
  onClose,
  onSave,
}: {
  target: User
  onClose: () => void
  onSave: (data: UserUpdate) => Promise<void>
}) {
  const [fullName, setFullName] = useState(target.full_name)
  const [email, setEmail] = useState(target.email)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')

    const changes: UserUpdate = {}

    if (fullName.trim() !== target.full_name) changes.full_name = fullName.trim()
    if (email.trim().toLowerCase() !== target.email.toLowerCase()) {
      changes.email = email.trim().toLowerCase()
    }

    if (!changes.full_name && !changes.email) {
      setError('Aucune modification détectée.')
      return
    }

    setLoading(true)

    try {
      await onSave(changes)
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Impossible de modifier cet utilisateur.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal title="Modifier l'utilisateur" onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <div>
          <label className="mb-1 block text-sm font-medium">Nom complet *</label>
          <input
            className={inputClass}
            required
            minLength={2}
            maxLength={120}
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
          />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium">Adresse e-mail *</label>
          <input
            className={inputClass}
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium">Rôle</label>
          <input className={inputClass} value={target.role === 'admin' ? 'Administrateur' : 'Agent'} disabled />
          <p className="mt-1 text-xs text-slate-400">Le rôle est fixe après la création du compte.</p>
        </div>

        {error && <p role="alert" className="text-sm text-red-600">{error}</p>}

        <div className="flex justify-end gap-3 pt-3">
          <button type="button" onClick={onClose} disabled={loading} className={secondaryButton}>Annuler</button>
          <button type="submit" disabled={loading} className={primaryButton}>
            {loading ? 'Modification...' : 'Enregistrer'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

// ============================================================
// FORMULAIRE TICKET
// ============================================================

function TicketForm({
  ticket,
  clients,
  agents,
  isAdmin,
  currentUser,
  onClose,
  onSave,
}: {
  ticket?: Ticket | null
  clients: Client[]
  agents: User[]
  isAdmin: boolean
  currentUser: User
  onClose: () => void
  onSave: (data: TicketCreate | TicketUpdate) => Promise<void>
}) {
  const [title, setTitle] = useState(ticket?.title ?? '')
  const [description, setDescription] = useState(ticket?.description ?? '')
  const [clientId, setClientId] = useState(String(ticket?.client_id ?? ''))
  const [assignedTo, setAssignedTo] = useState(ticket?.assigned_to ?? '')
  const [priority, setPriority] = useState<Ticket['priority']>(ticket?.priority ?? 'medium')
  const [status, setStatus] = useState<Ticket['status']>(ticket?.status ?? 'open')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const activeAgents = agents.filter((agent) => agent.role === 'agent' && agent.is_active)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setLoading(true)

    try {
      if (ticket && !isAdmin) {
        await onSave({ status, priority })
      } else if (ticket) {
        const data: TicketUpdate = {
          title: title.trim(),
          description: description.trim(),
          client_id: Number(clientId),
          priority,
          status,
        }

        if (assignedTo !== (ticket.assigned_to ?? '')) {
          data.assigned_to = assignedTo || null
        }

        await onSave(data)
      } else {
        const data: TicketCreate = {
          title: title.trim(),
          description: description.trim(),
          client_id: Number(clientId),
          priority,
          status,
        }

        if (isAdmin) data.assigned_to = assignedTo || null

        await onSave(data)
      }

      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Impossible d’enregistrer le ticket.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal title={ticket ? 'Modifier le ticket' : 'Créer un ticket'} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <div>
          <label className="mb-1 block text-sm font-medium">Titre *</label>
          <input className={inputClass} required disabled={!!ticket && !isAdmin} value={title} onChange={(e) => setTitle(e.target.value)} />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium">Description *</label>
          <textarea className={inputClass} rows={4} required maxLength={10000} disabled={!!ticket && !isAdmin} value={description} onChange={(e) => setDescription(e.target.value)} />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium">Client *</label>
          <select className={inputClass} required disabled={!!ticket && !isAdmin} value={clientId} onChange={(e) => setClientId(e.target.value)}>
            <option value="">Sélectionner un client</option>
            {clients.map((client) => <option key={client.id} value={client.id}>{client.name}</option>)}
          </select>
        </div>

        {isAdmin && (
          <div>
            <label className="mb-1 block text-sm font-medium">Agent responsable</label>
            <select className={inputClass} value={assignedTo} onChange={(e) => setAssignedTo(e.target.value)}>
              <option value="">Non affecté</option>
              {activeAgents.map((agent) => <option key={agent.id} value={agent.full_name}>{agent.full_name}</option>)}
            </select>
          </div>
        )}

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-sm font-medium">Priorité</label>
            <select className={inputClass} value={priority} onChange={(e) => setPriority(e.target.value as Ticket['priority'])}>
              <option value="low">Basse</option>
              <option value="medium">Moyenne</option>
              <option value="high">Haute</option>
              <option value="urgent">Urgente</option>
            </select>
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium">Statut</label>
            <select className={inputClass} value={status} onChange={(e) => setStatus(e.target.value as Ticket['status'])}>
              <option value="open">Ouvert</option>
              <option value="in_progress">En cours</option>
              <option value="resolved">Résolu</option>
              <option value="closed">Fermé</option>
            </select>
          </div>
        </div>

        {!isAdmin && !ticket && (
          <p className="rounded-xl bg-blue-50 p-3 text-xs text-blue-700">
            Ce ticket sera automatiquement affecté à votre compte : {currentUser.full_name}.
          </p>
        )}

        {error && <p role="alert" className="text-sm text-red-600">{error}</p>}

        <div className="flex justify-end gap-3 pt-3">
          <button type="button" onClick={onClose} disabled={loading} className={secondaryButton}>Annuler</button>
          <button type="submit" disabled={loading || (!ticket && clients.length === 0)} className={primaryButton}>
            {loading ? 'Enregistrement...' : 'Enregistrer'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

// ============================================================
// APPLICATION PRINCIPALE
// ============================================================

function App() {
  const [activePage, setActivePage] = useState<Page>('Vue générale')
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  const [user, setUser] = useState<User | null>(null)
  const [authLoading, setAuthLoading] = useState(true)
  const [authError, setAuthError] = useState('')

  const [dashboard, setDashboard] = useState<DashboardStatistics>(emptyDashboard)
  const [clients, setClients] = useState<Client[]>([])
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [users, setUsers] = useState<User[]>([])

  // Le chargement initial commence dès qu'une session authentifiée est disponible.
  const [dataLoading, setDataLoading] = useState(true)
  const [dataError, setDataError] = useState('')
  const [successMessage, setSuccessMessage] = useState('')

  const [showClientForm, setShowClientForm] = useState(false)
  const [editingClient, setEditingClient] = useState<Client | null>(null)
  const [deletingClient, setDeletingClient] = useState<Client | null>(null)

  const [showUserForm, setShowUserForm] = useState(false)
  const [editingUser, setEditingUser] = useState<User | null>(null)
  const [deletingUser, setDeletingUser] = useState<User | null>(null)
  const [userDeleteTicketCount, setUserDeleteTicketCount] = useState<number | null>(null)
  const [replacementUserId, setReplacementUserId] = useState('')
  const [userDeleteLoading, setUserDeleteLoading] = useState(false)
  const [userDeleteError, setUserDeleteError] = useState('')

  const [showTicketForm, setShowTicketForm] = useState(false)
  const [editingTicket, setEditingTicket] = useState<Ticket | null>(null)
  const [deletingTicket, setDeletingTicket] = useState<Ticket | null>(null)

  const [ticketSearch, setTicketSearch] = useState('')
  const [ticketStatusFilter, setTicketStatusFilter] = useState<Ticket['status'] | 'all'>('all')

  // ----------------------------------------------------------
  // AUTHENTIFICATION
  // ----------------------------------------------------------

  useEffect(() => {
    let active = true

    async function checkSession() {
      try {
        const currentUser = await getCurrentUser()
        if (active) setUser(currentUser)
      } catch (error) {
        logout()
        if (active && error instanceof ApiError && error.status !== 401) {
          setAuthError(error.message)
        }
      } finally {
        if (active) setAuthLoading(false)
      }
    }

    void checkSession()
    return () => { active = false }
  }, [])

  async function handleLogin(email: string, password: string) {
    const authenticatedUser = await login(email, password)
    setDataLoading(true)
    setUser(authenticatedUser)
    setAuthError('')
  }

  function handleLogout() {
    logout()
    setUser(null)
    setDashboard(emptyDashboard)
    setClients([])
    setTickets([])
    setUsers([])
    setDataLoading(false)
    setActivePage('Vue générale')
  }

  // ----------------------------------------------------------
  // CHARGEMENT DES DONNÉES
  // ----------------------------------------------------------

  // D?connexion automatique lorsqu'une requ?te signale un JWT invalide.
  useEffect(() => {
    function handleUnauthorized() {
      logout()
      setUser(null)
      setDashboard(emptyDashboard)
      setClients([])
      setTickets([])
      setUsers([])
      setDataLoading(false)
      setActivePage('Vue générale')
      setAuthError('Votre session a expiré. Veuillez vous reconnecter.')
      setDataError('')
      setSuccessMessage('')
    }

    window.addEventListener('clientpulse:unauthorized', handleUnauthorized)

    return () => {
      window.removeEventListener('clientpulse:unauthorized', handleUnauthorized)
    }
  }, [])

  async function refreshData() {
    if (!user) return

    setDataLoading(true)
    setDataError('')

    try {
      const [dashboardData, clientData, ticketData] = await Promise.all([
        getDashboard(),
        getClients(0, 100),
        getTickets(0, 100),
      ])

      setDashboard(dashboardData)
      setClients(clientData)
      setTickets(ticketData)
    } catch (error) {
      setDataError(error instanceof Error ? error.message : 'Erreur de chargement.')
      throw error
    } finally {
      setDataLoading(false)
    }
  }

  async function refreshUsers() {
    if (user?.role !== 'admin') return
    const data = await getUsers()
    setUsers(data)
  }

  // Chargement automatique des données principales après authentification.
  // Les mises à jour d'état sont effectuées après les réponses asynchrones,
  // ce qui évite les mises à jour synchrones interdites dans un effet React.
  useEffect(() => {
    if (!user) return

    let active = true

    async function loadData() {
      try {
        const [dashboardData, clientData, ticketData] = await Promise.all([
          getDashboard(),
          getClients(0, 100),
          getTickets(0, 100),
        ])

        if (!active) return

        setDashboard(dashboardData)
        setClients(clientData)
        setTickets(ticketData)
        setDataError('')
      } catch (error) {
        if (active) {
          setDataError(error instanceof Error ? error.message : 'Erreur de chargement.')
        }
      } finally {
        if (active) setDataLoading(false)
      }
    }

    void loadData()

    return () => {
      active = false
    }
  }, [user])

  // Chargement différé des utilisateurs lorsque l'administrateur ouvre
  // la page Utilisateurs ou Tickets.
  useEffect(() => {
    if (activePage !== 'Utilisateurs' && activePage !== 'Tickets') return
    if (user?.role !== 'admin') return

    let active = true

    async function loadUsers() {
      try {
        const data = await getUsers()
        if (active) setUsers(data)
      } catch (error) {
        if (active) {
          setDataError(
            error instanceof Error
              ? error.message
              : 'Impossible de charger les utilisateurs.',
          )
        }
      }
    }

    void loadUsers()

    return () => {
      active = false
    }
  }, [activePage, user])

  // ----------------------------------------------------------
  // DONNÉES DÉRIVÉES
  // ----------------------------------------------------------

  const clientsById = useMemo(
    () => new Map(clients.map((client) => [client.id, client])),
    [clients],
  )

  const activeAgents = useMemo(
    () => users.filter((item) => item.role === 'agent' && item.is_active),
    [users],
  )

  const filteredTickets = useMemo(() => {
    const query = ticketSearch.trim().toLowerCase()

    return tickets.filter((ticket) => {
      const clientName = clientsById.get(ticket.client_id)?.name ?? `Client #${ticket.client_id}`

      const matchesSearch =
        !query ||
        ticket.title.toLowerCase().includes(query) ||
        clientName.toLowerCase().includes(query) ||
        String(ticket.id).includes(query) ||
        (ticket.assigned_to ?? '').toLowerCase().includes(query)

      const matchesStatus = ticketStatusFilter === 'all' || ticket.status === ticketStatusFilter

      return matchesSearch && matchesStatus
    })
  }, [tickets, clientsById, ticketSearch, ticketStatusFilter])

  const recentTickets = useMemo(() => tickets.slice(0, 5), [tickets])

  const ticketData = [
    { name: 'Ouverts', value: dashboard.tickets.open },
    { name: 'En cours', value: dashboard.tickets.in_progress },
    { name: 'Résolus', value: dashboard.tickets.resolved },
    { name: 'Fermés', value: dashboard.tickets.closed },
  ]

  // ----------------------------------------------------------
  // ACTIONS CLIENTS
  // ----------------------------------------------------------

  async function handleSaveClient(data: ClientCreate | ClientUpdate) {
    if (editingClient) {
      await updateClient(editingClient.id, data as ClientUpdate)
      setSuccessMessage('Client modifié avec succès.')
    } else {
      await createClient(data as ClientCreate)
      setSuccessMessage('Client créé avec succès.')
    }

    await refreshData()
    setEditingClient(null)
    setShowClientForm(false)
  }

  async function handleDeleteClient() {
    if (!deletingClient) return

    try {
      await deleteClient(deletingClient.id)
      setDeletingClient(null)
      setSuccessMessage('Client supprimé avec succès.')
      await refreshData()
    } catch (error) {
      setDataError(error instanceof Error ? error.message : 'Impossible de supprimer ce client.')
    }
  }

  // ----------------------------------------------------------
  // ACTIONS UTILISATEURS
  // ----------------------------------------------------------

  async function handleCreateUser(data: UserCreate) {
    await createUser(data)
    await refreshUsers()
    setShowUserForm(false)
    setSuccessMessage('Compte agent créé avec succès.')
  }

  async function handleUpdateUser(data: UserUpdate) {
    if (!editingUser) return

    const updatedUser = await updateUser(editingUser.id, data)

    // Met à jour également la session si l'administrateur modifie son propre profil.
    if (user?.id === updatedUser.id) {
      setUser(updatedUser)
    }

    await refreshUsers()
    setEditingUser(null)
    setSuccessMessage('Utilisateur modifié avec succès.')
    setDataError('')
  }

  async function handleToggleUserStatus(target: User) {
    try {
      await updateUserStatus(target.id, !target.is_active)
      await refreshUsers()
      setSuccessMessage(target.is_active ? 'Compte désactivé.' : 'Compte activé.')
      setDataError('')
    } catch (error) {
      setDataError(error instanceof Error ? error.message : 'Impossible de modifier ce compte.')
    }
  }

  function openDeleteUser(target: User) {
    setDeletingUser(target)
    setUserDeleteTicketCount(null)
    setReplacementUserId('')
    setUserDeleteError('')
  }

  function closeDeleteUser() {
    if (userDeleteLoading) return

    setDeletingUser(null)
    setUserDeleteTicketCount(null)
    setReplacementUserId('')
    setUserDeleteError('')
  }

  async function handleDeleteUser() {
    if (!deletingUser) return

    setUserDeleteLoading(true)
    setUserDeleteError('')

    try {
      // Premier appel : sans agent de remplacement.
      // Le backend répond 409 si des tickets sont encore affectés.
      await deleteUser(
        deletingUser.id,
        replacementUserId ? Number(replacementUserId) : undefined,
      )

      setDeletingUser(null)
      setUserDeleteTicketCount(null)
      setReplacementUserId('')
      await refreshUsers()
      await refreshData()

      setSuccessMessage(`Le compte de ${deletingUser.full_name} a été supprimé.`)
      setDataError('')
    } catch (error) {
      const conflict = getDeleteConflict(error)

      if (conflict) {
        // Le backend exige une réaffectation avant la suppression.
        setUserDeleteTicketCount(conflict.ticket_count)
        setUserDeleteError(
          `Cet utilisateur possède ${conflict.ticket_count} ticket(s). Sélectionnez un agent actif pour les réaffecter.`,
        )
      } else {
        setUserDeleteError(
          error instanceof Error ? error.message : 'Impossible de supprimer cet utilisateur.',
        )
      }
    } finally {
      setUserDeleteLoading(false)
    }
  }

  // ----------------------------------------------------------
  // ACTIONS TICKETS
  // ----------------------------------------------------------

  async function handleCreateTicket(data: TicketCreate | TicketUpdate) {
    await createTicket(data as TicketCreate)
    await refreshData()
    setSuccessMessage('Ticket créé avec succès.')
    setDataError('')
  }

  async function handleUpdateTicket(data: TicketCreate | TicketUpdate) {
    if (!editingTicket) return

    await updateTicket(editingTicket.id, data as TicketUpdate)
    await refreshData()
    setEditingTicket(null)
    setSuccessMessage('Ticket modifié avec succès.')
    setDataError('')
  }

  async function handleDeleteTicket() {
    if (!deletingTicket) return

    try {
      await deleteTicket(deletingTicket.id)
      setDeletingTicket(null)
      await refreshData()
      setSuccessMessage('Ticket supprimé avec succès.')
    } catch (error) {
      setDataError(error instanceof Error ? error.message : 'Impossible de supprimer ce ticket.')
    }
  }

  // ----------------------------------------------------------
  // CHARGEMENT INITIAL
  // ----------------------------------------------------------

  if (authLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <div className="text-center">
          <Activity size={32} className="mx-auto animate-pulse text-blue-600" />
          <p className="mt-3 text-sm text-slate-500">Vérification de votre session...</p>
        </div>
      </div>
    )
  }

  if (!user) {
    return (
      <>
        <LoginScreen onLogin={handleLogin} />
        {authError && (
          <p className="fixed bottom-4 left-4 right-4 text-center text-sm text-red-600">
            {authError}
          </p>
        )}
      </>
    )
  }

  const isAdmin = user.role === 'admin'

  // ----------------------------------------------------------
  // INTERFACE
  // ----------------------------------------------------------

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">

      {/* MENU LATÉRAL */}
      <aside className={`fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-slate-200 bg-white transition-transform duration-300 ${
        mobileMenuOpen ? 'translate-x-0' : '-translate-x-full'
      } lg:translate-x-0`}>
        <div className="flex h-20 items-center gap-3 border-b border-slate-100 px-6">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-600 text-white shadow-lg shadow-blue-200">
            <Activity size={23} />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-slate-900">
              Client<span className="text-blue-600">Pulse</span>
            </h1>
            <p className="text-xs text-slate-400">Customer management</p>
          </div>
          <button onClick={() => setMobileMenuOpen(false)} className="ml-auto text-slate-400 lg:hidden" aria-label="Fermer le menu">
            <X size={20} />
          </button>
        </div>

        <div className="px-4 py-7">
          <p className="mb-3 px-3 text-xs font-semibold uppercase tracking-wider text-slate-400">Menu principal</p>
          <nav className="space-y-1">
            {navigation.filter((item) => !item.adminOnly || isAdmin).map((item) => {
              const Icon = item.icon
              const selected = activePage === item.label

              return (
                <button
                  key={item.label}
                  onClick={() => {
                    setActivePage(item.label)
                    setMobileMenuOpen(false)
                    setDataError('')
                    setSuccessMessage('')
                  }}
                  className={`flex w-full items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium transition ${
                    selected ? 'bg-blue-600 text-white shadow-md shadow-blue-200' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-900'
                  }`}
                >
                  <Icon size={19} />
                  {item.label}
                  {item.label === 'Tickets' && (
                    <span className={`ml-auto rounded-full px-2 py-0.5 text-xs ${
                      selected ? 'bg-white/20 text-white' : 'bg-orange-100 text-orange-600'
                    }`}>
                      {tickets.length}
                    </span>
                  )}
                </button>
              )
            })}
          </nav>
        </div>

        <div className="mt-auto space-y-1 border-t border-slate-100 p-4">
          <button onClick={handleLogout} className="mt-4 flex w-full items-center gap-3 rounded-xl bg-slate-50 p-3 text-left transition hover:bg-red-50">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-100 text-sm font-bold text-blue-700">
              {initials(user.full_name)}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold text-slate-800">{user.full_name}</p>
              <p className="text-xs text-slate-400">{isAdmin ? 'Administrateur' : 'Agent'}</p>
            </div>
            <LogOut size={17} className="text-slate-400" />
          </button>
        </div>
      </aside>

      {mobileMenuOpen && (
        <button className="fixed inset-0 z-40 bg-slate-900/30 lg:hidden" onClick={() => setMobileMenuOpen(false)} aria-label="Fermer le menu" />
      )}

      {/* CONTENU PRINCIPAL */}
      <main className="min-h-screen lg:ml-64">
        <header className="sticky top-0 z-30 flex h-20 items-center justify-between border-b border-slate-200 bg-white/90 px-5 backdrop-blur-xl sm:px-8">
          <div className="flex items-center gap-3">
            <button onClick={() => setMobileMenuOpen(true)} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 lg:hidden" aria-label="Ouvrir le menu">
              <Menu size={22} />
            </button>
            <div>
              <p className="text-sm text-slate-400">Espace de travail</p>
              <p className="font-semibold text-slate-800">{activePage}</p>
            </div>
          </div>

          <div className="flex items-center gap-3 sm:gap-5">
            <button onClick={() => void refreshData().catch(() => undefined)} className="rounded-xl p-2.5 text-slate-500 hover:bg-slate-100" title="Actualiser les données" aria-label="Actualiser">
              <RefreshCw size={19} className={dataLoading ? 'animate-spin' : ''} />
            </button>
            <button className="relative rounded-xl p-2.5 text-slate-500 hover:bg-slate-100" aria-label="Notifications">
              <Bell size={20} />
            </button>
            <div className="hidden h-8 border-l border-slate-200 sm:block" />
            <button onClick={handleLogout} className="flex items-center gap-2" title="Se déconnecter">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-blue-100 text-sm font-bold text-blue-700">
                {initials(user.full_name)}
              </div>
              <span className="hidden text-sm font-medium sm:block">{user.full_name}</span>
              <ChevronDown size={16} className="hidden text-slate-400 sm:block" />
            </button>
          </div>
        </header>

        <div className="mx-auto max-w-7xl space-y-7 p-5 sm:p-8">
          {/* EN-TÊTE */}
          <section className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
            <div>
              <h2 className="text-2xl font-bold tracking-tight text-slate-900">
                Bonjour, {user.full_name.split(' ')[0]} 👋
              </h2>
              <p className="mt-1 text-sm text-slate-500">Voici un aperçu de l'activité de votre espace ClientPulse.</p>
            </div>
            <div className="flex flex-wrap gap-3">
             <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-medium text-slate-600 shadow-sm">
              <CalendarDays size={17} />
               Vue d'ensemble
             </div>
        </div>          </section>

          {dataError && (
            <div role="alert" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {dataError}
            </div>
          )}

          {successMessage && (
            <div className="flex items-center justify-between rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
              {successMessage}
              <button onClick={() => setSuccessMessage('')} aria-label="Fermer"><X size={16} /></button>
            </div>
          )}

          {dataLoading && <p className="text-sm text-slate-400">Actualisation des données...</p>}

          {/* TABLEAU DE BORD */}
          {activePage === 'Vue générale' && (
            <>
              <section className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
                {[
                  { title: 'Total clients', value: dashboard.clients.total, description: `${dashboard.clients.active} actifs · ${dashboard.clients.prospect} prospects`, icon: Users, style: 'bg-blue-50 text-blue-600' },
                  { title: 'Tickets ouverts', value: dashboard.tickets.open, description: 'Demandes en attente', icon: MessageSquare, style: 'bg-orange-50 text-orange-600' },
                  { title: 'Tickets en cours', value: dashboard.tickets.in_progress, description: 'Demandes traitées', icon: Activity, style: 'bg-violet-50 text-violet-600' },
                  { title: 'Taux de résolution', value: `${dashboard.resolution_rate.toLocaleString('fr-FR', { maximumFractionDigits: 1 })} %`, description: 'Tickets résolus ou clôturés', icon: ShieldCheck, style: 'bg-emerald-50 text-emerald-600' },
                ].map((stat, index) => {
                  const Icon = stat.icon
                  return (
                    <article key={stat.title} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-1 hover:shadow-md">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium text-slate-500">{stat.title}</span>
                        <div className={`rounded-xl p-2.5 ${stat.style}`}><Icon size={20} /></div>
                      </div>
                      <div className="mt-5 flex items-end justify-between gap-2">
                        <p className="text-3xl font-bold tracking-tight text-slate-900">{stat.value}</p>
                        {index === 3 ? <ArrowUpRight size={17} className="mb-1 text-emerald-600" /> : <ArrowDownRight size={17} className="mb-1 text-blue-600" />}
                      </div>
                      <p className="mt-1 text-xs text-slate-400">{stat.description}</p>
                    </article>
                  )
                })}
              </section>

              <Suspense
                fallback={
                  <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-400">
                    Chargement des graphiques...
                  </div>
                }
              >
                <DashboardCharts
                  ticketData={ticketData}
                  totalTickets={dashboard.tickets.total}
                />
              </Suspense>

              <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 p-5">
                  <div>
                    <h3 className="font-bold text-slate-900">Tickets récents</h3>
                    <p className="mt-1 text-xs text-slate-400">Dernières demandes de vos clients</p>
                  </div>
                  <button onClick={() => setActivePage('Tickets')} className="text-sm font-semibold text-blue-600">Voir tous les tickets →</button>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[700px] text-left">
                    <thead className="bg-slate-50 text-xs uppercase tracking-wider text-slate-400">
                      <tr>{['Ticket', 'Client', 'Date', 'Priorité', 'Statut'].map((heading) => <th key={heading} className="px-5 py-4 font-semibold">{heading}</th>)}</tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {recentTickets.map((ticket) => {
                        const clientName = clientsById.get(ticket.client_id)?.name ?? `Client #${ticket.client_id}`
                        return (
                          <tr key={ticket.id} className="hover:bg-slate-50/70">
                            <td className="px-5 py-4">
                              <p className="text-xs font-semibold text-blue-600">#TK-{String(ticket.id).padStart(4, '0')}</p>
                              <p className="mt-1 text-sm font-medium text-slate-800">{ticket.title}</p>
                            </td>
                            <td className="px-5 py-4 text-sm text-slate-600">{clientName}</td>
                            <td className="px-5 py-4 text-xs text-slate-500">{formatDate(ticket.created_at)}</td>
                            <td className="px-5 py-4"><span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${priorityColor(priorityLabel(ticket.priority))}`}>{priorityLabel(ticket.priority)}</span></td>
                            <td className="px-5 py-4"><span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${statusColor(statusLabel(ticket.status))}`}>{statusLabel(ticket.status)}</span></td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
                {recentTickets.length === 0 && <p className="p-8 text-center text-sm text-slate-400">Aucun ticket enregistré.</p>}
              </section>
            </>
          )}

          {/* CLIENTS */}
          {activePage === 'Clients' && (
            <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 p-5">
                <div>
                  <h3 className="font-bold text-slate-900">Gestion des clients</h3>
                  <p className="mt-1 text-xs text-slate-400">{clients.length} client(s)</p>
                </div>
                {isAdmin && (
                  <button
                    onClick={() => {
                      setEditingClient(null)
                      setShowClientForm(true)
                    }}
                    className={primaryButton}
                  >
                    <Plus size={17} /> Nouveau client
                  </button>
                )}
              </div>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[850px] text-left">
                  <thead className="bg-slate-50 text-xs uppercase tracking-wider text-slate-400">
                    <tr>{['Nom', 'Entreprise', 'E-mail', 'Téléphone', 'Statut', 'Actions'].map((heading) => <th key={heading} className="px-5 py-4 font-semibold">{heading}</th>)}</tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {clients.map((client) => (
                      <tr key={client.id} className="hover:bg-slate-50/70">
                        <td className="px-5 py-4 text-sm font-semibold text-slate-800">{client.name}</td>
                        <td className="px-5 py-4 text-sm text-slate-600">{client.company || '—'}</td>
                        <td className="px-5 py-4 text-sm text-slate-600">{client.email}</td>
                        <td className="px-5 py-4 text-sm text-slate-600">{client.phone || '—'}</td>
                        <td className="px-5 py-4">
                          <span className="rounded-full bg-blue-50 px-2.5 py-1 text-xs font-semibold text-blue-600">{client.status}</span>
                        </td>
                        <td className="px-5 py-4">
                          <div className="flex gap-2">
                            {isAdmin && (
                              <button
                                onClick={() => {
                                  setEditingClient(client)
                                  setShowClientForm(true)
                                }}
                                className="rounded-lg p-2 text-blue-600 hover:bg-blue-50"
                                title="Modifier"
                              >
                                <Pencil size={16} />
                              </button>
                            )}
                            {isAdmin && (
                              <button onClick={() => setDeletingClient(client)} className="rounded-lg p-2 text-red-500 hover:bg-red-50" title="Supprimer">
                                <Trash2 size={16} />
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {clients.length === 0 && <p className="p-8 text-center text-sm text-slate-400">Aucun client enregistré.</p>}
            </section>
          )}

          {/* TICKETS */}
          {activePage === 'Tickets' && (
            <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 p-5">
                <div>
                  <h3 className="font-bold text-slate-900">Gestion des tickets</h3>
                  <p className="mt-1 text-xs text-slate-400">{filteredTickets.length} ticket(s) affiché(s)</p>
                </div>
                <button onClick={() => { setEditingTicket(null); setShowTicketForm(true) }} disabled={clients.length === 0} className={primaryButton}>
                  <Plus size={17} /> Nouveau ticket
                </button>
              </div>

              <div className="flex flex-col gap-3 border-b border-slate-100 p-5 sm:flex-row">
                <div className="relative flex-1">
                  <Search size={17} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input className={`${inputClass} pl-10`} placeholder="Rechercher un ticket, client ou responsable..." value={ticketSearch} onChange={(e) => setTicketSearch(e.target.value)} />
                </div>
                <select className={`${inputClass} sm:w-52`} value={ticketStatusFilter} onChange={(e) => setTicketStatusFilter(e.target.value as Ticket['status'] | 'all')}>
                  <option value="all">Tous les statuts</option>
                  <option value="open">Ouvert</option>
                  <option value="in_progress">En cours</option>
                  <option value="resolved">Résolu</option>
                  <option value="closed">Fermé</option>
                </select>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full min-w-[950px] text-left">
                  <thead className="bg-slate-50 text-xs uppercase tracking-wider text-slate-400">
                    <tr>{['Ticket', 'Client', 'Responsable', 'Date', 'Priorité', 'Statut', 'Actions'].map((heading) => <th key={heading} className="px-5 py-4 font-semibold">{heading}</th>)}</tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {filteredTickets.map((ticket) => {
                      const clientName = clientsById.get(ticket.client_id)?.name ?? `Client #${ticket.client_id}`
                      return (
                        <tr key={ticket.id} className="transition hover:bg-slate-50/70">
                          <td className="px-5 py-4">
                            <p className="text-xs font-semibold text-blue-600">#TK-{String(ticket.id).padStart(4, '0')}</p>
                            <p className="mt-1 text-sm font-medium text-slate-800">{ticket.title}</p>
                          </td>
                          <td className="px-5 py-4 text-sm text-slate-600">{clientName}</td>
                          <td className="px-5 py-4 text-sm text-slate-600">{ticket.assigned_to || 'Non affecté'}</td>
                          <td className="px-5 py-4 text-xs text-slate-500">{formatDate(ticket.created_at)}</td>
                          <td className="px-5 py-4"><span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${priorityColor(priorityLabel(ticket.priority))}`}>{priorityLabel(ticket.priority)}</span></td>
                          <td className="px-5 py-4"><span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${statusColor(statusLabel(ticket.status))}`}>{statusLabel(ticket.status)}</span></td>
                          <td className="px-5 py-4">
                            <div className="flex gap-2">
                              <button onClick={() => setEditingTicket(ticket)} className="rounded-lg p-2 text-blue-600 hover:bg-blue-50" title="Modifier"><Pencil size={16} /></button>
                              {isAdmin && <button onClick={() => setDeletingTicket(ticket)} className="rounded-lg p-2 text-red-500 hover:bg-red-50" title="Supprimer"><Trash2 size={16} /></button>}
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>

              {filteredTickets.length === 0 && <p className="p-8 text-center text-sm text-slate-400">Aucun ticket ne correspond à votre recherche.</p>}
              <div className="border-t border-slate-100 px-5 py-4 text-xs text-slate-400">
                {isAdmin ? 'Administrateur : accès global et gestion complète des tickets.' : 'Agent : seuls les tickets qui vous sont affectés sont affichés.'}
              </div>
            </section>
          )}

          {/* UTILISATEURS */}
          {activePage === 'Utilisateurs' && isAdmin && (
            <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 p-5">
                <div>
                  <h3 className="font-bold text-slate-900">Gestion des utilisateurs</h3>
                  <p className="mt-1 text-xs text-slate-400">{users.length} compte(s)</p>
                </div>
                <button onClick={() => setShowUserForm(true)} className={primaryButton}>
                  <Plus size={17} /> Ajouter un agent
                </button>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full min-w-[900px] text-left">
                  <thead className="bg-slate-50 text-xs uppercase tracking-wider text-slate-400">
                    <tr>{['Utilisateur', 'E-mail', 'Rôle', 'Statut', 'Création', 'Actions'].map((heading) => <th key={heading} className="px-5 py-4 font-semibold">{heading}</th>)}</tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {users.map((item) => (
                      <tr key={item.id} className="hover:bg-slate-50/70">
                        <td className="px-5 py-4">
                          <div className="flex items-center gap-3">
                            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-blue-100 text-xs font-bold text-blue-700">{initials(item.full_name)}</div>
                            <span className="text-sm font-semibold text-slate-800">{item.full_name}</span>
                          </div>
                        </td>
                        <td className="px-5 py-4 text-sm text-slate-600">{item.email}</td>
                        <td className="px-5 py-4 text-sm text-slate-600">{item.role === 'admin' ? 'Administrateur' : 'Agent'}</td>
                        <td className="px-5 py-4">
                          <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${item.is_active ? 'bg-emerald-50 text-emerald-600' : 'bg-red-50 text-red-600'}`}>
                            {item.is_active ? 'Actif' : 'Désactivé'}
                          </span>
                        </td>
                        <td className="px-5 py-4 text-xs text-slate-500">{formatDate(item.created_at)}</td>
                        <td className="px-5 py-4">
                          <div className="flex flex-wrap items-center gap-2">
                            <button
                              onClick={() => setEditingUser(item)}
                              className="rounded-lg p-2 text-blue-600 hover:bg-blue-50"
                              title="Modifier"
                              aria-label={`Modifier ${item.full_name}`}
                            >
                              <Pencil size={16} />
                            </button>

                            {item.role === 'agent' && (
                              <>
                                <button
                                  onClick={() => void handleToggleUserStatus(item)}
                                  className={item.is_active
                                    ? 'rounded-lg bg-red-50 px-3 py-2 text-xs font-semibold text-red-600 hover:bg-red-100'
                                    : 'rounded-lg bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-600 hover:bg-emerald-100'}
                                >
                                  {item.is_active ? 'Désactiver' : 'Activer'}
                                </button>

                                <button
                                  onClick={() => openDeleteUser(item)}
                                  className="rounded-lg p-2 text-red-500 hover:bg-red-50"
                                  title="Supprimer"
                                  aria-label={`Supprimer ${item.full_name}`}
                                >
                                  <Trash2 size={16} />
                                </button>
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {users.length === 0 && <p className="p-8 text-center text-sm text-slate-400">Aucun utilisateur enregistré.</p>}
            </section>
          )}

          <footer className="pb-3 text-center text-xs text-slate-400">
            © 2026 ClientPulse. Tous droits réservés.
          </footer>
        </div>
      </main>

      {/* ======================================================
          MODALES
      ====================================================== */}

      {showClientForm && isAdmin && (
        <ClientForm
          client={editingClient}
          onClose={() => { setShowClientForm(false); setEditingClient(null) }}
          onSave={handleSaveClient}
        />
      )}

      {showUserForm && (
        <UserForm onClose={() => setShowUserForm(false)} onSave={handleCreateUser} />
      )}

      {editingUser && (
        <EditUserForm
          target={editingUser}
          onClose={() => setEditingUser(null)}
          onSave={handleUpdateUser}
        />
      )}

      {showTicketForm && (
        <TicketForm
          clients={clients}
          agents={activeAgents}
          isAdmin={isAdmin}
          currentUser={user}
          onClose={() => setShowTicketForm(false)}
          onSave={handleCreateTicket}
        />
      )}

      {editingTicket && (
        <TicketForm
          ticket={editingTicket}
          clients={clients}
          agents={activeAgents}
          isAdmin={isAdmin}
          currentUser={user}
          onClose={() => setEditingTicket(null)}
          onSave={handleUpdateTicket}
        />
      )}

      {deletingTicket && (
        <Modal title="Supprimer le ticket" onClose={() => setDeletingTicket(null)}>
          <p className="text-sm text-slate-600">
            Voulez-vous vraiment supprimer le ticket <strong>#{deletingTicket.id} – {deletingTicket.title}</strong> ?
          </p>
          <p className="mt-2 text-xs text-red-500">Cette action est irréversible.</p>
          <div className="mt-6 flex justify-end gap-3">
            <button onClick={() => setDeletingTicket(null)} className={secondaryButton}>Annuler</button>
            <button onClick={() => void handleDeleteTicket()} className={dangerButton}>Supprimer</button>
          </div>
        </Modal>
      )}

      {deletingClient && (
        <Modal title="Supprimer le client" onClose={() => setDeletingClient(null)}>
          <p className="text-sm text-slate-600">
            Voulez-vous vraiment supprimer le client <strong>{deletingClient.name}</strong> ?
          </p>
          <p className="mt-2 text-xs text-red-500">La suppression peut être refusée si des tickets sont liés à ce client.</p>
          <div className="mt-6 flex justify-end gap-3">
            <button onClick={() => setDeletingClient(null)} className={secondaryButton}>Annuler</button>
            <button onClick={() => void handleDeleteClient()} className={dangerButton}>Supprimer</button>
          </div>
        </Modal>
      )}

      {/* MODALE DE SUPPRESSION D'UTILISATEUR */}
      {deletingUser && (
        <Modal title="Supprimer un utilisateur" onClose={closeDeleteUser}>
          <div className="space-y-4">
            <p className="text-sm text-slate-600">
              Voulez-vous vraiment supprimer le compte de{' '}
              <strong>{deletingUser.full_name}</strong> ?
            </p>

            {userDeleteTicketCount === null ? (
              <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-800">
                La suppression sera refusée si cet agent possède encore des tickets.
                Le système vérifiera les affectations avant de supprimer le compte.
              </p>
            ) : (
              <>
                <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
                  <p className="text-sm font-semibold text-amber-900">
                    Réaffectation nécessaire
                  </p>
                  <p className="mt-1 text-sm text-amber-800">
                    {userDeleteTicketCount} ticket(s) sont actuellement affectés à cet agent.
                    Sélectionnez un agent actif pour les récupérer.
                  </p>
                </div>

                <div>
                  <label className="mb-2 block text-sm font-medium text-slate-700">
                    Nouvel agent responsable *
                  </label>
                  <select
                    className={inputClass}
                    value={replacementUserId}
                    onChange={(e) => setReplacementUserId(e.target.value)}
                    required
                  >
                    <option value="">Sélectionner un agent</option>
                    {activeAgents
                      .filter((agent) => agent.id !== deletingUser.id)
                      .map((agent) => (
                        <option key={agent.id} value={agent.id}>
                          {agent.full_name} — {agent.email}
                        </option>
                      ))}
                  </select>
                  {activeAgents.filter((agent) => agent.id !== deletingUser.id).length === 0 && (
                    <p className="mt-2 text-xs text-red-600">
                      Aucun autre agent actif disponible. Activez ou créez un agent avant de continuer.
                    </p>
                  )}
                </div>
              </>
            )}

            {userDeleteError && (
              <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-600">
                {userDeleteError}
              </p>
            )}

            <p className="text-xs text-red-500">
              Cette opération est irréversible. Le compte sera définitivement supprimé.
            </p>

            <div className="flex justify-end gap-3 pt-2">
              <button
                onClick={closeDeleteUser}
                disabled={userDeleteLoading}
                className={secondaryButton}
              >
                Annuler
              </button>
              <button
                onClick={() => void handleDeleteUser()}
                disabled={
                  userDeleteLoading ||
                  (userDeleteTicketCount !== null && !replacementUserId) ||
                  (userDeleteTicketCount !== null && activeAgents.filter((agent) => agent.id !== deletingUser.id).length === 0)
                }
                className={dangerButton}
              >
                {userDeleteLoading ? 'Suppression...' : 'Confirmer la suppression'}
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}

export default App
