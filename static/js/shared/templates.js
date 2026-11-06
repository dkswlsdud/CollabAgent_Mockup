

// 화면별 HTML은 처음 실행할 때 한 번 읽고 메모리에 보관합니다.
export const templateFiles = [
  'pages/calendar/calendar-my',
  'pages/calendar/calendar-team',
  'components/calendar',
  'components/common',
  'components/request-detail',
  'components/request-options',
  'components/requests',
  'pages/history/history',
  'pages/auth/login',
  'pages/requests/request-detail',
  'pages/requests/request-new',
  'pages/requests/request-renegotiate',
  'pages/requests/requests-received',
  'pages/requests/requests-sent',
  'pages/schedules/schedule-detail',
  'pages/schedules/schedule-new',
];
export const templates = new Map();

export async function loadViews() {
  if (templates.size) return;
  const files = await Promise.all(
    templateFiles.map(async (name) => {
      const response = await fetch(`/static/html/${name}.html`);
      if (!response.ok) throw new Error(`화면 파일을 읽을 수 없습니다: ${name}`);
      return response.text();
    }),
  );

  // 원문을 사용해야 {{disabledAttribute}} 같은 동적 속성도 보존됩니다.
  const templatePattern = /<template\s+id="([\w-]+)">([\s\S]*?)<\/template>/g;
  for (const html of files) {
    for (const [, name, content] of html.matchAll(templatePattern)) {
      if (templates.has(name)) throw new Error(`중복된 화면 이름입니다: ${name}`);
      templates.set(name, content.trim());
    }
  }
}

export function view(name, values = {}) {
  if (!templates.has(name)) throw new Error(`등록되지 않은 화면입니다: ${name}`);

  // HTML 조각과 일반 문자열을 모두 받습니다. 사용자 입력은 호출부에서 esc()로 보호합니다.
  // 한 번만 치환하므로 사용자 문자열 속 {{...}}를 다시 해석하지 않습니다.
  return templates.get(name).replace(/{{\s*(\w+)\s*}}/g, (_, key) => {
    if (!Object.hasOwn(values, key)) {
      throw new Error(`${name} 화면에 필요한 값이 없습니다: ${key}`);
    }
    return String(values[key] ?? '');
  });
}
