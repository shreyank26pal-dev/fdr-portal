import { DemoAccountPreset, User } from './types';

export const DEMO_ACCOUNTS: DemoAccountPreset[] = [
  {
    email: 'college1@aicte-demo.in',
    password: 'Password@123',
    role: 'INSTITUTION',
    label: 'Institution 1 — Demo Institute of Technology, Pune',
    subtitle: 'Has active FDRs, maturing FDR (~95d), and eligible extra intake FDR for release',
    badgeColor: 'bg-blue-100 text-blue-900 border-blue-300',
  },
  {
    email: 'officer@aicte-demo.in',
    password: 'Password@123',
    role: 'SCRUTINY_OFFICER',
    label: 'Scrutiny Officer — Dr. Meera Nair (AICTE HQ)',
    subtitle: 'Work queue, Dual-Truth verification, Flag Confirmation, Recommend Release',
    badgeColor: 'bg-indigo-100 text-indigo-900 border-indigo-300',
  },
  {
    email: 'approver@aicte-demo.in',
    password: 'Password@123',
    role: 'APPROVING_AUTHORITY',
    label: 'Approving Authority — Prof. Arvind Deshmukh (Director)',
    subtitle: 'Final FDR activation sign-off & Two-Person Rule Refund Sanction',
    badgeColor: 'bg-purple-100 text-purple-900 border-purple-300',
  },
  {
    email: 'ro.western@aicte-demo.in',
    password: 'Password@123',
    role: 'REGIONAL_OFFICER',
    label: 'Regional Officer — Sh. Suresh Kulkarni (Western RO)',
    subtitle: 'Western region oversight, SLA escalation tickets & compliance monitoring',
    badgeColor: 'bg-teal-100 text-teal-900 border-teal-300',
  },
  {
    email: 'bank.sbi@aicte-demo.in',
    password: 'Password@123',
    role: 'BANK',
    label: 'Bank Nodal Officer — State Bank of India (SBI)',
    subtitle: 'Blind Bank Confirmation Queue & Core Banking Ledger verification',
    badgeColor: 'bg-amber-100 text-amber-900 border-amber-300',
  },
  {
    email: 'bank.canara@aicte-demo.in',
    password: 'Password@123',
    role: 'BANK',
    label: 'Bank Nodal Officer — Canara Bank',
    subtitle: 'Manual nodal bank confirmation portal (non-API bank)',
    badgeColor: 'bg-orange-100 text-orange-900 border-orange-300',
  },
  {
    email: 'admin@aicte-demo.in',
    password: 'Password@123',
    role: 'ADMIN',
    label: 'System Administrator — AICTE e-Governance Cell',
    subtitle: 'Time-Travel Clock, Rule Engine Config, Bank Outage & Audit Tamper Simulator',
    badgeColor: 'bg-rose-100 text-rose-900 border-rose-300',
  },
  {
    email: 'auditor@aicte-demo.in',
    password: 'Password@123',
    role: 'AUDITOR',
    label: 'External CAG / Vigilance Auditor (Read-Only)',
    subtitle: 'Cryptographic SHA-256 Hash-Chained Audit Ledger & Reports',
    badgeColor: 'bg-emerald-100 text-emerald-900 border-emerald-300',
  },
  {
    email: 'college8@aicte-demo.in',
    password: 'Password@123',
    role: 'INSTITUTION',
    label: 'Institution 8 — Has Open Compliance Case (Blocks Release)',
    subtitle: 'Demonstrates guarded release blocked by open court/vigilance case',
    badgeColor: 'bg-sky-100 text-sky-900 border-sky-300',
  },
  {
    email: 'college5@aicte-demo.in',
    password: 'Password@123',
    role: 'INSTITUTION',
    label: 'Institution 5 — Renewal Overdue (Institution Locked HTTP 423)',
    subtitle: 'Demonstrates automatic lock until overdue FDR renewal is submitted',
    badgeColor: 'bg-red-100 text-red-900 border-red-300',
  },
];

const TOKEN_KEY = 'securedeposit_jwt';
export const SESSION_EXPIRED_EVENT = 'securedeposit:session-expired';

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

export async function apiFetch<T = any>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers = new Headers(options.headers || {});
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  if (
    options.body &&
    !(options.body instanceof FormData) &&
    !headers.has('Content-Type')
  ) {
    headers.set('Content-Type', 'application/json');
  }

  const res = await fetch(path.startsWith('/api') || path.startsWith('/health') ? path : `/api/v1${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    let errText = `HTTP ${res.status}`;
    try {
      const data = await res.json();
      if (data?.detail) {
        errText =
          typeof data.detail === 'string'
            ? data.detail
            : JSON.stringify(data.detail);
      }
    } catch {
      // ignore json parse error
    }
    const error: any = new Error(errText);
    error.status = res.status;
    // Expired / invalid session anywhere in the app -> back to the login page
    if (res.status === 401 && token && !path.includes('/auth/login')) {
      setToken(null);
      window.dispatchEvent(new CustomEvent(SESSION_EXPIRED_EVENT));
    }
    throw error;
  }

  const contentType = res.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    return res.json();
  }
  return (await res.text()) as unknown as T;
}

export async function loginWithCredentials(
  email: string,
  password = 'Password@123',
  otp?: string
): Promise<{ access_token: string; user: User }> {
  const data = await apiFetch<{ access_token: string; user: User }>('/auth/login', {
    method: 'POST',
    body: JSON.stringify(otp ? { email, password, otp } : { email, password }),
  });
  setToken(data.access_token);
  return data;
}

export async function fetchBlobWithHeaders(path: string): Promise<{
  blob: Blob;
  url: string;
  sha256: string | null;
  integrity: string | null;
  filename: string | null;
}> {
  const token = getToken();
  const headers = new Headers();
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  const fullPath = path.startsWith('/api') ? path : `/api/v1${path}`;
  const res = await fetch(fullPath, { headers });
  if (!res.ok) {
    throw new Error(`Failed to download document (HTTP ${res.status})`);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const sha256 = res.headers.get('X-Content-SHA256');
  const integrity = res.headers.get('X-Integrity');
  const disp = res.headers.get('Content-Disposition');
  let filename: string | null = null;
  if (disp && disp.includes('filename=')) {
    filename = disp.split('filename=')[1].replace(/["']/g, '').trim();
  }
  return { blob, url, sha256, integrity, filename };
}

export async function loadSampleAsFile(filename: string): Promise<File> {
  const res = await fetch(`/api/v1/meta/samples/${encodeURIComponent(filename)}`);
  if (!res.ok) {
    throw new Error(`Could not load sample ${filename}`);
  }
  const blob = await res.blob();
  const mime = filename.endsWith('.png') ? 'image/png' : 'application/pdf';
  return new File([blob], filename, { type: mime });
}

export function formatINR(amount: number | string | null | undefined): string {
  if (amount === null || amount === undefined || amount === '') return '—';
  const num = typeof amount === 'string' ? parseFloat(amount) : amount;
  if (Number.isNaN(num)) return String(amount);
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(num);
}

/**
 * Modern Web Guidance: Light-Dismiss a Dialog (`closedby="any"` + fallback for browsers without closedBy support)
 */
export function openLightDismissDialog(dialog: HTMLDialogElement | null): void {
  if (!dialog) return;
  if (!('closedBy' in HTMLDialogElement.prototype) && !dialog.dataset.fallbackBound) {
    dialog.dataset.fallbackBound = 'true';
    dialog.addEventListener('click', (event: MouseEvent) => {
      if (event.target !== dialog) return;
      const rect = dialog.getBoundingClientRect();
      const isDialogContent =
        rect.top <= event.clientY &&
        event.clientY <= rect.top + rect.height &&
        rect.left <= event.clientX &&
        event.clientX <= rect.left + rect.width;
      if (isDialogContent) return;
      dialog.close();
    });
  }
  if (!dialog.open) {
    dialog.showModal();
  }
}

/**
 * Modern Web Guidance: Validate Input After Interaction (`:user-invalid` + ARIA synchronization)
 */
export function initUserInvalidSync(): void {
  if (typeof document === 'undefined') return;
  const syncAria = (el: EventTarget | null) => {
    if (el instanceof HTMLElement && typeof el.matches === 'function') {
      if (el instanceof HTMLInputElement || el instanceof HTMLSelectElement || el instanceof HTMLTextAreaElement) {
        try {
          el.setAttribute('aria-invalid', el.matches(':user-invalid') ? 'true' : 'false');
        } catch {
          // ignore selector unsupported
        }
      }
    }
  };
  document.addEventListener('blur', (e) => syncAria(e.target), true);
  document.addEventListener('input', (e) => {
    if (e.target instanceof HTMLElement && e.target.hasAttribute('aria-invalid')) {
      syncAria(e.target);
    }
  });
}
