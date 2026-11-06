import { $ } from '../shared/dom.js';

// 화면 이동과 별개로 사이드바 표시 상태만 관리합니다.
export const sidebarPreferenceKey = 'collab.sidebarCollapsed';

export function resetNavigationMenus() {
  for (const [button, submenu] of [['#request-nav', '#request-submenu'], ['#schedule-toggle', '#schedule-submenu']]) {
    $(submenu).hidden = false;
    $(button).setAttribute('aria-expanded', 'true');
  }
}

export function toggleNavigationMenu(button, submenu) {
  const collapsed = !$(submenu).hidden;
  $(submenu).hidden = collapsed;
  $(button).setAttribute('aria-expanded', String(!collapsed));
}

export function setSidebarCollapsed(collapsed, persist = true) {
  document.body.classList.toggle('sidebar-collapsed', collapsed);

  const button = $('#sidebar-toggle');
  const label = collapsed ? '사이드바 펼치기' : '사이드바 접기';
  button.setAttribute('aria-expanded', String(!collapsed));
  button.setAttribute('aria-label', label);
  button.title = label;
  $('#workspace-sidebar').inert = collapsed;

  if (persist) {
    try {
      localStorage.setItem(sidebarPreferenceKey, String(collapsed));
    } catch {
      // 저장을 허용하지 않는 브라우저에서도 접기/펼치기는 동작합니다.
    }
  }
}

export function initializeSidebar() {
  resetNavigationMenus();
  // Every visit starts expanded; the toggle still works for the current visit.
  setSidebarCollapsed(false, false);
  $('#sidebar-toggle').addEventListener('click', () => {
    setSidebarCollapsed(!document.body.classList.contains('sidebar-collapsed'));
  });
}


