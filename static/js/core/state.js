export const state = {
  // 로그인 정보와 각 화면이 공유하는 데이터입니다.
  user: null,
  employees: [],
  departments: [],
  requests: [],
  consents: [],
  newScheduleCount: 0,
  page: 'login',
  filter: 'all',
  requestBox: 'received',
  routeId: null,
  scope: 'team',
  calendarEmployeeId: '',
  calendarDepartment: '',
  activeDetail: null,

  month: new Date().getFullYear() + '-' + String(new Date().getMonth() + 1).padStart(2, '0'),
  renderId: 0,
  submitting: false,
  loginDestination: '/requests/received',
};
