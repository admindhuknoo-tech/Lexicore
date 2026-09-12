"""LexiCore License Authority GUI for offline Desktop license issuance.

Administrator-only utility. It never belongs in the customer installer.
"""
from __future__ import annotations

import csv
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    from license_admin.issue_license import PREFIX, fp_from_installation_id, issue_license_file
except ModuleNotFoundError:  # direct execution from license_admin/
    from issue_license import PREFIX, fp_from_installation_id, issue_license_file

PLAN_OPTIONS = {
    'Trial 30 Hari': ('desktop-trial-30d', 30),
    'Desktop Tahunan (365 Hari)': ('desktop-annual', 365),
    'Desktop Perpetual': ('desktop-perpetual', 0),
}


def default_authority_dir() -> Path:
    if os.name == 'nt':
        return Path(r'C:\LexiCore-License-Authority')
    return Path.home() / 'LexiCore-License-Authority'


def safe_customer_slug(name: str) -> str:
    cleaned = re.sub(r'[^A-Za-z0-9._-]+', '-', (name or '').strip()).strip('-._')
    return cleaned[:48] or 'customer'


def ledger_path(authority_dir: Path) -> Path:
    return authority_dir / 'license_ledger.csv'


def append_ledger(
    authority_dir: Path,
    *,
    license_id: str,
    customer_name: str,
    contact: str,
    installation_id: str,
    plan_label: str,
    plan_code: str,
    expires_days: int,
    output_file: Path,
) -> None:
    path = ledger_path(authority_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    row = {
        'issued_at_utc': datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        'license_id': license_id,
        'customer_name': customer_name.strip(),
        'contact': contact.strip(),
        'installation_id': installation_id.strip(),
        'plan_label': plan_label,
        'plan_code': plan_code,
        'expires_days': expires_days,
        'license_file': str(output_file),
        'status': 'ISSUED',
    }
    with path.open('a', newline='', encoding='utf-8-sig') as fh:
        writer = csv.DictWriter(fh, fieldnames=list(row))
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def create_license_for_customer(
    *,
    authority_dir: str | Path,
    customer_name: str,
    contact: str,
    installation_id: str,
    plan_label: str,
) -> dict:
    authority = Path(authority_dir).expanduser().resolve()
    if plan_label not in PLAN_OPTIONS:
        raise ValueError('INVALID_PLAN')
    if not customer_name.strip():
        raise ValueError('CUSTOMER_NAME_REQUIRED')
    normalized_fp = fp_from_installation_id(installation_id)
    normalized_installation_id = PREFIX + normalized_fp
    private_key = authority / 'license_private_key.pem'
    if not private_key.is_file():
        raise FileNotFoundError(f'Private key tidak ditemukan: {private_key}')
    plan_code, expires_days = PLAN_OPTIONS[plan_label]

    # Generate the signed license first with a temporary unique output name based on a
    # provisional suffix. The issuer returns the real license_id, then the file is
    # atomically renamed to a human-friendly name containing that license_id.
    issued_dir = authority / 'issued'
    issued_dir.mkdir(parents=True, exist_ok=True)
    customer_slug = safe_customer_slug(customer_name)
    provisional = issued_dir / f'LexiCore-{customer_slug}-{datetime.now().strftime("%Y%m%d%H%M%S%f")}.lic'
    result = issue_license_file(
        private_key=private_key,
        installation_id=normalized_installation_id,
        output=provisional,
        plan=plan_code,
        expires_days=expires_days,
    )
    final_path = issued_dir / f"LexiCore-{result['license_id']}-{customer_slug}.lic"
    if final_path.exists():
        provisional.unlink(missing_ok=True)
        raise FileExistsError(f'License file sudah ada: {final_path}')
    provisional.replace(final_path)
    result['output'] = str(final_path)
    append_ledger(
        authority,
        license_id=result['license_id'],
        customer_name=customer_name,
        contact=contact,
        installation_id=normalized_installation_id,
        plan_label=plan_label,
        plan_code=plan_code,
        expires_days=expires_days,
        output_file=final_path,
    )
    return result


def open_folder(path: Path) -> None:
    path = path.resolve()
    if os.name == 'nt':
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == 'darwin':
        subprocess.Popen(['open', str(path)])
    else:
        subprocess.Popen(['xdg-open', str(path)])


class LicenseAuthorityApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title('LexiCore License Authority')
        self.geometry('760x610')
        self.minsize(700, 560)
        self.authority_var = tk.StringVar(value=str(default_authority_dir()))
        self.customer_var = tk.StringVar()
        self.contact_var = tk.StringVar()
        self.installation_var = tk.StringVar()
        self.plan_var = tk.StringVar(value='Trial 30 Hari')
        self.result_var = tk.StringVar(value='Belum ada lisensi diterbitkan.')
        self.last_output: Path | None = None
        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self, padding=18)
        outer.pack(fill='both', expand=True)
        ttk.Label(outer, text='LexiCore License Authority', font=('Segoe UI', 17, 'bold')).pack(anchor='w')
        ttk.Label(
            outer,
            text='Penerbit lisensi offline Desktop — private key tetap hanya di komputer administrator.',
        ).pack(anchor='w', pady=(2, 18))

        form = ttk.Frame(outer)
        form.pack(fill='x')
        self._row(form, 0, 'Folder Authority', self.authority_var, browse=True)
        self._row(form, 1, 'Nama Pengguna / Firma', self.customer_var)
        self._row(form, 2, 'Email / WhatsApp', self.contact_var)
        self._row(form, 3, 'Installation ID', self.installation_var)

        ttk.Label(form, text='Paket Lisensi').grid(row=4, column=0, sticky='w', pady=8)
        ttk.Combobox(
            form,
            textvariable=self.plan_var,
            values=list(PLAN_OPTIONS),
            state='readonly',
            width=42,
        ).grid(row=4, column=1, sticky='ew', pady=8)
        form.columnconfigure(1, weight=1)

        actions = ttk.Frame(outer)
        actions.pack(fill='x', pady=(18, 12))
        ttk.Button(actions, text='GENERATE LICENSE', command=self.generate).pack(side='left')
        ttk.Button(actions, text='Buka Folder Issued', command=self.open_issued).pack(side='left', padx=8)
        ttk.Button(actions, text='Buka Ledger', command=self.open_ledger).pack(side='left')

        ttk.Separator(outer).pack(fill='x', pady=10)
        ttk.Label(outer, text='Hasil', font=('Segoe UI', 11, 'bold')).pack(anchor='w')
        ttk.Label(outer, textvariable=self.result_var, wraplength=700, justify='left').pack(anchor='w', pady=(8, 0))

        info = (
            'Alur: pengguna mengirim Installation ID → admin menerbitkan .lic → pengguna import .lic.\n'
            'File license terikat ke satu device. Private key tidak pernah dikirim ke pengguna atau installer.'
        )
        ttk.Label(outer, text=info, wraplength=700, foreground='#555').pack(anchor='w', pady=(24, 0))

    def _row(self, parent, row: int, label: str, var: tk.StringVar, browse: bool = False) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky='w', pady=8, padx=(0, 12))
        entry = ttk.Entry(parent, textvariable=var)
        entry.grid(row=row, column=1, sticky='ew', pady=8)
        if browse:
            ttk.Button(parent, text='Browse', command=self.browse_authority).grid(row=row, column=2, padx=(8, 0))

    def browse_authority(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.authority_var.get() or str(Path.home()))
        if chosen:
            self.authority_var.set(chosen)

    def generate(self) -> None:
        try:
            result = create_license_for_customer(
                authority_dir=self.authority_var.get(),
                customer_name=self.customer_var.get(),
                contact=self.contact_var.get(),
                installation_id=self.installation_var.get(),
                plan_label=self.plan_var.get(),
            )
            self.last_output = Path(result['output'])
            self.result_var.set(
                f"BERHASIL\nLicense ID: {result['license_id']}\n"
                f"Device: {result['installation_id']}\nFile: {result['output']}"
            )
            messagebox.showinfo('LexiCore License Authority', 'License berhasil diterbitkan.')
        except Exception as exc:
            self.result_var.set(f'GAGAL: {exc}')
            messagebox.showerror('Gagal menerbitkan license', str(exc))

    def open_issued(self) -> None:
        path = Path(self.authority_var.get()).expanduser() / 'issued'
        path.mkdir(parents=True, exist_ok=True)
        open_folder(path)

    def open_ledger(self) -> None:
        path = ledger_path(Path(self.authority_var.get()).expanduser())
        if not path.exists():
            messagebox.showinfo('Ledger', 'Ledger belum dibuat. Terbitkan license pertama terlebih dahulu.')
            return
        if os.name == 'nt':
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            open_folder(path.parent)


def main() -> int:
    app = LicenseAuthorityApp()
    app.mainloop()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
