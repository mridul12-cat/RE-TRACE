/* Presentation shell only. Verification and demo handlers stay in index.html. */
let shellStatusPending = false;
let shellHealth = {state:'pending'};
function renderShellStatus() {
  const message=document.getElementById('overview-health');
  const labels=document.querySelectorAll('[data-ledger-status]');
  if (shellHealth.state === 'pending') {
    REUI.set(message,'ui.checking_api_and_ledger_status');
    labels.forEach(node => REUI.set(node,'shell.checkLedger'));
  } else if (shellHealth.state === 'failed') {
    REUI.set(message,'shell.unavailable'); labels.forEach(node => REUI.set(node,'shell.ledgerUnavailable'));
  } else {
    const values={mode:REUI.ref(shellHealth.mode),state:REUI.ref(shellHealth.connection),time:shellHealth.at.toLocaleTimeString(REUI.getLocale() === 'tr' ? 'tr-TR' : 'en-GB',{hour:'2-digit',minute:'2-digit'})};
    REUI.set(message,'shell.health',values);labels.forEach(node => REUI.set(node,'shell.ledger',values));
  }
}
document.addEventListener('retrace:localechange',renderShellStatus);

async function refreshShellStatus() {
  if (shellStatusPending) return;
  shellStatusPending = true;
  const refresh = document.getElementById('overview-refresh');
  const message = document.getElementById('overview-health');
  refresh.disabled = true;
  shellHealth={state:'pending'};renderShellStatus();
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 8000);
  try {
    const response = await fetch('/health', { signal: controller.signal, cache: 'no-store' });
    if (!response.ok) throw new Error('Health check unavailable');
    const health = await response.json();
    const ledger = health.blockchain;
    if (!ledger || typeof ledger.is_connected !== 'boolean' || health.status !== 'HEALTHY') {
      throw new Error('Incomplete health response');
    }
    shellHealth={state:'loaded',mode:ledger.is_local_simulation === true ? 'shell.simulation' : 'shell.service',connection:ledger.is_connected ? 'shell.available' : 'shell.disconnected',at:new Date()};
    renderShellStatus();
  } catch (error) {
    shellHealth={state:'failed'};renderShellStatus();
  } finally {
    clearTimeout(timeout);
    shellStatusPending = false;
    refresh.disabled = false;
  }
}

function setMobileDrawer(open, restoreFocus = true) {
  const drawer = document.getElementById('mobile-drawer');
  const trigger = document.getElementById('mobile-menu-btn');
  const wasOpen = !drawer.classList.contains('hidden');
  drawer.classList.toggle('hidden', !open);
  trigger.setAttribute('aria-expanded', String(open));
  document.body.style.overflow = open ? 'hidden' : '';
  document.getElementById('main-content').inert = open;
  document.querySelector('.shell-mobile').inert = open;
  document.getElementById('app-sidebar').inert = open;
  if (open) drawer.querySelector('button').focus();
  else if (wasOpen && restoreFocus) trigger.focus();
}

document.addEventListener('DOMContentLoaded', () => {
  // Decorative icons should never become part of a control's accessible name.
  document.querySelectorAll('#app-sidebar i, .shell-mobile i, #mobile-drawer i').forEach(icon => {
    icon.setAttribute('aria-hidden', 'true');
  });
  const drawer = document.getElementById('mobile-drawer');
  drawer.addEventListener('click', event => {
    if (event.target === drawer) setMobileDrawer(false);
  });
  drawer.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      event.preventDefault();
      setMobileDrawer(false);
    } else if (event.key === 'Tab') {
      const controls = [...drawer.querySelectorAll('button, a[href]')];
      const first = controls[0];
      const last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
  });
  window.matchMedia('(min-width: 1024px)').addEventListener('change', event => {
    if (event.matches) setMobileDrawer(false, false);
  });
  refreshShellStatus();
});
