// Run with: node --experimental-vm-modules tests/frontend-smoke.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const elements = new Map();
function element(selector) {
  if (!elements.has(selector)) elements.set(selector, {
    innerHTML: '', textContent: '', value: '', dataset: {},
    classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
    querySelectorAll() { return []; },
    handlers: {}, attributes: {}, addEventListener(name, callback) { this.handlers[name] = callback; }, setAttribute(name, value) { this.attributes[name] = value; }, focus() {},
    open: false,
    showModal() { this.open = true; },
    close() { this.open = false; this.handlers.close?.(); },
    getBoundingClientRect() { return {left:100,right:660,top:100,bottom:500}; },
  });
  return elements.get(selector);
}
const location = { pathname: '/', search: '', hash: '' };
const errors = [];
const user = { id: 1, login_id:'tester', name: '테스트', department: '개발팀' };
const calls = [];
let failAnalysis = false;
let expired = false;
let failSchedule = false;
let scheduleDetailIsNew=false;
let scheduleDetailOwner=1;
let clickedScheduleButtons=[];
let checkedConditions = [];
let intakeQuestions = [];
let questionButtons = [];
let failResponse = false;
let failConsentDetail = false;
let failConsentReply = false;
let simulateRecoordination = false;
let failGeneration = false;
let consentDetails = null;
let newScheduleCount = 0;
let calendarRows = [];
const requestDetail = { request: { id:10, requester_id:1, assignee_id:2, requester_name:'테스트', assignee_name:'동료', due_at:'2026-11-06T18:00', status:'PENDING', task_content:'배너 제작', original_text:'배너 5개', conditions_json:[{key:'quantity',label:'수량',value:5,constraint:'SOFT'}] }, rounds:[], alternatives:[], consents:[], result:null, response:null, analysis:{summary:'빈 시간 10시간', recommended_response:'ACCEPT', conflicts:[]} };
requestDetail.request.conditions_json.push({key:'deadline',label:'마감',constraint:'HARD'});
requestDetail.schedule_timeline = {start_at:'2026-11-02T00:00:00',end_at:'2026-11-06T18:00:00',current_at:'2026-11-02T12:00:00',schedules:[
  {id:8,title:'여러 날 진행하는 업무',type:'WORK',start_at:'2026-11-01T09:00:00',end_at:'2026-11-04T18:00:00',priority:'HIGH',workload:'HIGH',status:'IN_PROGRESS'},
  {id:9,title:'팀 회의',type:'MEETING',start_at:'2026-11-05T14:00:00',end_at:'2026-11-05T15:00:00',priority:'MEDIUM',workload:'LOW',status:'SCHEDULED'},
]};
const context = vm.createContext({
  console: { ...console, error: error => errors.push(error) },
  URLSearchParams, Intl, setTimeout: () => 0, clearTimeout() {}, location,
  history: { pushState(_, __, url) { location.pathname = url; }, replaceState(_, __, url) { location.pathname = url; } },
  localStorage: { getItem() { return 'true'; }, setItem() {} },
  document: { querySelector: element, querySelectorAll: selector => selector === '[data-remove-question]' ? questionButtons : selector === '[data-schedule-id="3"]' ? clickedScheduleButtons : selector.endsWith('input[name="keep"]:checked') ? checkedConditions.map(value => ({value})) : [], body: element('body') },
  window: { addEventListener() {}, confirm() { return true; }, alert() {} },
  fetch: async (url, options = {}) => {
    calls.push({url, ...options});
    if (url === '/api/requests/analyze' && failAnalysis) return {ok:false,status:502,json:async () => ({error:'AI 연결 실패'})};
    if (url === '/api/requests' && expired) return {ok:false,status:401,json:async () => ({error:'로그인이 만료되었습니다.'})};
    if (url === '/api/schedules/3' && failSchedule) return {ok:false,status:404,json:async () => ({error:'일정을 찾을 수 없습니다.'})};
    if (url === '/api/requests/10/action' && failResponse) return {ok:false,status:409,json:async () => ({error:'응답을 저장하지 못했습니다.'})};
    if (url === '/api/consents/1_1' && options.method === 'POST' && failConsentReply) return {ok:false,status:409,json:async()=>({error:'거부 사유를 저장하지 못했습니다.'})};
    if (url === '/api/requests/10/action' && options.method === 'POST') {
      const action = JSON.parse(options.body).action;
      if (action === 'generate' && failGeneration) return {ok:false,status:502,json:async()=>({error:'AI 생성에 실패했습니다.'})};
      if (action === 'restart_after_rejection' && simulateRecoordination) {
        requestDetail.request.needs_recoordination = false;
        requestDetail.rounds = [{id:2,round_no:2,status:'IN_PROGRESS',request_snapshot_json:{related_party_rejections:requestDetail.request.consent_rejections}}];
        requestDetail.request.consent_rejections = [];
        requestDetail.alternatives = [];
        requestDetail.consents = [];
        requestDetail.result = null;
      }
    }
    if (url === '/api/consents/1_1' && failConsentDetail) return {ok:false,status:403,json:async()=>({error:'본인에게 전달된 동의 요청만 확인할 수 있습니다.'})};
    if (url.startsWith('/static/')) return { ok: true, text: async () => fs.readFileSync(path.join(process.cwd(), url.slice(1)), 'utf8') };
    const data = url === '/api/requests/analyze' ? { task_content:'배너 제작', assignee_id:2, due_at:'2026-11-06T18:00', conditions_json:[{key:'quantity',label:'수량',value:5,constraint:'SOFT'}], questions:intakeQuestions, method:'LLM', ready:true }
      : url === '/api/requests' && options.method === 'POST' ? {id:10}
      : url === '/api/requests/10' ? JSON.parse(JSON.stringify(requestDetail))
      : url === '/api/requests/10/action' ? {ok:true}
      : url === '/api/schedules/3' && ['PUT','DELETE'].includes(options.method) ? {ok:true}
      : url === '/api/schedules/3' ? {schedule:{id:3,employee_id:scheduleDetailOwner,is_new:scheduleDetailIsNew,type:'MEETING',title:'디자인 검토',employee_name:'테스트',department:'개발팀',start_at:'2026-11-06T10:00',end_at:'2026-11-06T11:00',due_at:null,priority:'HIGH',status:'SCHEDULED',requester_name:null,memo:'<script>unsafe</script>'}}
      : url === '/api/auth/me' ? { user }
      : url === '/api/auth/login' ? { user }
      : url === '/api/auth/logout' ? { ok:true }
      : url === '/api/employees' ? { employees: [user, {id:2,name:'동료',department:user.department}, {id:3,name:'다른 부서 직원',department:'다른팀'}], departments: [user.department,'다른팀'] }
      : url === '/api/requests' ? { requests: [] }
      : url === '/api/requests/10/read' || url === '/api/consents/1_1/read' ? {ok:true}
      : url === '/api/consents/1_1/calendar-settings' ? {ok:true,completed:false}
      : url === '/api/consents/1_1' && options.method === 'POST' ? {ok:true,completed:false}
      : url === '/api/consents/1_1' ? consentDetails
      : url === '/api/consents' ? { consents: [] }
      : url === '/api/schedules/notifications' ? {count:newScheduleCount}
      : url === '/api/schedules/notifications/read' ? {count:newScheduleCount=Math.max(0,newScheduleCount-JSON.parse(options.body).schedule_ids.length)}
      : url.startsWith('/api/schedules?') ? { schedules: calendarRows }
      : null;
    assert.ok(data, `Unexpected API call: ${url}`);
    return { ok: true, json: async () => data };
  },
});
const modules = new Map();
function collect(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const file = path.resolve(dir, entry.name);
    if (entry.isDirectory()) collect(file);
    else if (file.endsWith('.js')) modules.set(file, new vm.SourceTextModule(fs.readFileSync(file, 'utf8'), { context, identifier: file }));
  }
}
(async () => {
  collect('static/js');
  const entry = modules.get(path.resolve('static/js/app.js'));
  await entry.link((specifier, parent) => {
    const module = modules.get(path.resolve(path.dirname(parent.identifier), specifier));
    assert.ok(module, `Missing module: ${specifier}`);
    return module;
  });
  await entry.evaluate();
  // Flush startup's template and API promises.
  await new Promise(resolve => setImmediate(resolve));
  const router = modules.get(path.resolve('static/js/core/router.js')).namespace;
  const state = modules.get(path.resolve('static/js/core/state.js')).namespace.state;
  assert.equal(state.user, null);
  assert.equal(location.pathname, '/login');
  assert.ok(element('#auth-root').innerHTML.includes('auth-login-id'));
  assert.ok(!calls.some(call => call.url === '/api/auth/me'));
  assert.ok(!calls.some(call => call.url === '/api/employees'));
  const loginAuth = modules.get(path.resolve('static/js/pages/auth.js')).namespace;
  for (const [name,id] of [['김민지','minji.kim'],['이서준','seojun.lee'],['박지훈','jihoon.park'],['정하은','haeun.jung'],['최유진','yujin.choi']]) {
    assert.ok(element('#auth-root').innerHTML.includes(name));
    loginAuth.fillDemo(id);
    assert.equal(element('#auth-login-id').value,id);
    assert.equal(element('#auth-password').value,'Collab123!');
  }
  assert.ok(fs.readFileSync('static/html/index.html','utf8').includes('data-request-box="consents"'));
  element('#auth-login-id').value = 'tester';
  element('#auth-password').value = 'password';
  await element('#auth-form').handlers.submit({preventDefault(){}});
  assert.equal(state.user.id, 1);
  assert.equal(element('#profile-name').textContent, '테스트');
  assert.equal(element('#profile-login-id').textContent, 'tester');
  assert.equal(element('#profile-team').textContent, '개발팀');
  assert.equal(element('#profile-status').hidden, false);
  assert.equal(element('#sidebar-toggle').attributes['aria-expanded'], 'true');
  assert.equal(element('#workspace-sidebar').inert, false);
  assert.equal(location.pathname, '/requests/received');
  assert.equal(element('#request-submenu').hidden, false);
  assert.equal(element('#schedule-submenu').hidden, false);
  for (const [button, submenu] of [['#request-nav','#request-submenu'], ['#schedule-toggle','#schedule-submenu']]) {
    element(button).handlers.click();
    assert.equal(element(submenu).hidden, true);
    assert.equal(element(button).attributes['aria-expanded'], 'false');
    assert.equal(location.pathname, '/requests/received');
    element(button).handlers.click();
    assert.equal(element(submenu).hidden, false);
    assert.equal(element(button).attributes['aria-expanded'], 'true');
  }
  const sentStatuses = ['SUBMITTED','SUBMITTED','SUBMITTED','SUBMITTED','NEGOTIATING','NEGOTIATING','AWAITING_CONFIRMATION','AGREED','AGREED','REJECTED'];
  state.requests = [...sentStatuses.map((status,i) => ({id:i+1,requester_id:1,assignee_id:2,status,task_content:'보낸 요청 '+(i+1),original_text:'요청',requester_name:'테스트',assignee_name:'동료',assignee_department:'개발팀'})),
    ...['SUBMITTED','AGREED'].map((status,i) => ({id:20+i,requester_id:2,assignee_id:1,status,task_content:'받은 요청 '+i,original_text:'요청',requester_name:'동료',assignee_name:'테스트',assignee_department:'개발팀'}))];
  await router.navigatePath('/requests/sent');
  const statCounts = [...element('#app').innerHTML.matchAll(/<div class="stat[^"]*">[\s\S]*?<label>(.*?)<\/label>[\s\S]*?<strong>\s*(\d+)/g)].map(match => Number(match[2]));
  assert.deepEqual(statCounts, [10,4,3,3]);
  assert.equal(statCounts[0], statCounts.slice(1).reduce((sum,value) => sum + value,0));
  const inbox = modules.get(path.resolve('static/js/pages/inbox.js')).namespace;
  inbox.setFilter('COMPLETED');
  assert.equal((element('#app').innerHTML.match(/class="request-card(?:\s[^"]*)?"/g) || []).length, 3);
  assert.ok(element('#app').innerHTML.includes('보낸 요청 8'));
  assert.ok(element('#app').innerHTML.includes('보낸 요청 9'));
  assert.ok(element('#app').innerHTML.includes('보낸 요청 10'));
  await router.navigatePath('/requests/received');
  state.requests = [];
  state.filter = 'all';
  for (const url of ['/requests/received', '/requests/new', '/calendar/team', '/calendar/my', '/schedules/new', '/history']) {
    await router.navigatePath(url);
    assert.equal(location.pathname, url);
    assert.ok(element('#app').innerHTML.length, `Empty page: ${url}`);
    assert.ok(!element('#app').innerHTML.includes('screen-error'), `Failed page: ${url}`);
  }
  assert.equal(router.resolveRoute('/requests/12/renegotiate').id, 12);
  assert.equal(router.resolveRoute('/schedules/3').page, 'schedule-detail');
  await router.navigatePath('/calendar/team');
  assert.ok(element('#app').innerHTML.includes('calendar-employee-select'));
  assert.ok(element('#app').innerHTML.includes('동료'));
  assert.ok(!element('#app').innerHTML.includes('다른 부서 직원'));
  await element('#calendar-employee-select').handlers.change({target:{value:'2'}});
  assert.equal(state.calendarEmployeeId, '2');
  assert.ok(calls.at(-1).url.includes('employee_id=2'));
  assert.ok(element('#app').innerHTML.includes('calendar-department-select'));
  await element('#calendar-department-select').handlers.change({target:{value:'다른팀'}});
  assert.equal(state.calendarEmployeeId, '');
  assert.equal(new URLSearchParams(calls.at(-1).url.split('?')[1]).get('department'), '다른팀');
  assert.ok(element('#app').innerHTML.includes('다른 부서 직원'));
  assert.ok(!element('#app').innerHTML.includes('>동료</option>'));
  await element('#calendar-employee-select').handlers.change({target:{value:'3'}});
  assert.ok(calls.at(-1).url.includes('employee_id=3'));
  await element('#calendar-department-select').handlers.change({target:{value:user.department}});
  assert.equal(state.calendarEmployeeId, '');
  await element('#calendar-employee-select').handlers.change({target:{value:''}});
  assert.ok(!calls.at(-1).url.includes('employee_id='));
  const calendar = modules.get(path.resolve('static/js/pages/calendar.js')).namespace;
  const layout = modules.get(path.resolve('static/js/shared/calendar-layout.js')).namespace;
  const multi = {id:100,type:'WORK',title:'연속 작업',employee_name:'동료',start_at:'2026-11-06T09:00:00',end_at:'2026-11-10T18:00:00'};
  const midnight = {...multi,id:101,end_at:'2026-11-10T00:00:00'};
  const overlap = {...multi,id:102,start_at:'2026-11-07T10:00:00',end_at:'2026-11-09T12:00:00'};
  const weeks = layout.calendarWeeks('2026-11',[multi,midnight,overlap]);
  const segments = weeks.flatMap(week => week.segments).filter(s => s.schedule.id===100);
  assert.equal(segments.length,2);
  assert.equal(segments[0].startColumn,6);
  assert.equal(segments[0].endColumn,7);
  assert.equal(segments[0].continuesAfter,true);
  assert.equal(segments[1].startColumn,1);
  assert.equal(segments[1].endColumn,3);
  assert.equal(segments[1].continuesBefore,true);
  assert.equal(weeks[1].segments.find(s => s.schedule.id===101).endColumn,2);
  for (const week of weeks) for (const a of week.segments) for (const b of week.segments) {
    if (a !== b && a.startColumn <= b.endColumn && a.endColumn >= b.startColumn) assert.notEqual(a.lane,b.lane);
  }
  const clipped = layout.calendarWeeks('2026-11',[{...multi,start_at:'2026-10-29T09:00:00',end_at:'2026-11-03T18:00:00'}])[0].segments[0];
  assert.equal(clipped.startColumn,1);
  assert.equal(clipped.endColumn,3);
  assert.equal(clipped.continuesBefore,true);
  const grid = modules.get(path.resolve('static/js/components/calendar-grid.js')).namespace;
  const bandHtml = grid.calendarGrid('2026-11',[multi],'2026-11-02');
  assert.equal((bandHtml.match(/data-schedule-id="100"/g)||[]).length,2);
  assert.ok(bandHtml.includes('grid-column: 6 / 8'));
  const calendarHtml = element('#app').innerHTML;
  const calendarMonth = state.month;
  await calendar.openSchedule({id:3});
  assert.equal(location.pathname, '/calendar/team');
  assert.equal(state.page, 'calendar');
  assert.equal(state.scope, 'team');
  assert.equal(state.month, calendarMonth);
  assert.equal(element('#app').innerHTML, calendarHtml);
  assert.equal(element('#schedule-dialog').open, true);
  assert.ok(element('#schedule-dialog-body').innerHTML.includes('디자인 검토'));
  assert.ok(!element('#schedule-dialog-body').innerHTML.includes('<dt>마감</dt>'));
  assert.ok(element('#schedule-dialog-body').innerHTML.includes('&lt;script&gt;'));
  assert.ok(element('#schedule-dialog-body').innerHTML.includes('schedule-edit'));
  element('#schedule-edit').handlers.click();
  assert.ok(element('#schedule-dialog-body').innerHTML.includes('schedule-editor'));
  element('#edit-schedule-title').value = '수정 일정';
  element('#edit-schedule-start').value = '2026-11-06T10:00';
  element('#edit-schedule-end').value = '2026-11-09T11:00';
  await element('#schedule-editor').handlers.submit({preventDefault(){}});
  const updateCall = calls.find(call => call.url==='/api/schedules/3' && call.method==='PUT');
  assert.equal(JSON.parse(updateCall.body).end_at,'2026-11-09T11:00');
  assert.equal(element('#schedule-dialog').open,false);
  assert.equal(location.pathname,'/calendar/team');
  await calendar.openSchedule({id:3});
  await element('#schedule-delete').handlers.click();
  assert.ok(calls.some(call => call.url==='/api/schedules/3' && call.method==='DELETE'));
  assert.equal(element('#schedule-dialog').open,false);
  state.user = {...user,id:2};
  await calendar.openSchedule({id:3});
  assert.ok(!element('#schedule-dialog-body').innerHTML.includes('id="schedule-edit"'));
  assert.ok(!element('#schedule-dialog-body').innerHTML.includes('id="schedule-delete"'));
  state.user = user;
  element('#schedule-dialog-close').handlers.click();
  assert.equal(element('#schedule-dialog').open, false);
  failSchedule = true;
  await calendar.openSchedule({id:3});
  assert.equal(element('#schedule-dialog-body').textContent, '일정을 찾을 수 없습니다.');
  assert.equal(location.pathname, '/calendar/team');
  failSchedule = false;
  await router.navigatePath('/history');
  assert.equal(element('#schedule-dialog').open, false);
  await router.navigatePath('/requests/new');
  assert.ok(element('#app').innerHTML.includes('id="request-team"'));
  element('#request-team').value = '다른팀';
  element('#request-team').handlers.change();
  assert.ok(element('#request-person').innerHTML.includes('다른 부서 직원'));
  assert.ok(!element('#request-person').innerHTML.includes('>동료 ·'));
  assert.equal(element('#request-person').value,'');
  element('#request-team').value = user.department;
  element('#request-team').handlers.change();
  element('#request-person').value = '2';
  element('#request-title').value = '직접 작성한 검토 요청';
  element('#request-original').value = '동료에게 배너 5개 요청';
  intakeQuestions=[{key:'clarification_optional',question:'어떤 고객을 인터뷰하나요?'}];
  const questionDelete=element('#test-question-delete');
  questionDelete.dataset.removeQuestion='clarification_optional';
  questionButtons=[questionDelete];
  await element('#request-analyze').handlers.click();
  assert.ok(element('#request-questions').innerHTML.includes('질문 삭제'));
  questionDelete.handlers.click();
  assert.ok(!element('#request-questions').innerHTML.includes('어떤 고객을 인터뷰하나요?'));
  intakeQuestions=[]; questionButtons=[];
  assert.equal(element('#request-review').hidden, false);
  assert.equal(element('#request-title').value, '직접 작성한 검토 요청');
  assert.ok(element('#request-conditions').innerHTML.includes('수량'));
  failAnalysis = true;
  await element('#request-analyze').handlers.click();
  assert.equal(element('#request-submit').disabled, true);
  assert.equal(element('#request-review').hidden, true);
  assert.equal(element('#request-error').textContent, 'AI 연결 실패');
  failAnalysis = false;
  await element('#request-analyze').handlers.click();
  element('#hard-deadline').value='HARD';
  await element('#request-form').handlers.submit({preventDefault(){}});
  const submitted = JSON.parse(calls.find(c => c.url === '/api/requests' && c.method === 'POST').body);
  assert.equal(submitted.conditions_json[0].constraint,'HARD');
  assert.equal(submitted.conditions_json[1].value, 5);
  assert.equal(submitted.conditions_json[1].constraint,'HARD');
  assert.equal(submitted.task_content,'직접 작성한 검토 요청');
  assert.equal(submitted.assignee_department,user.department);
  assert.equal(location.pathname, '/requests/10');
  assert.ok(!element('#app').innerHTML.includes('request-schedule'));
  assert.ok(!element('#app').innerHTML.includes('availability-chart'));
  assert.ok(!element('#app').innerHTML.includes('response-waiting'));
  assert.ok(!element('#app').innerHTML.includes('수행자의 응답을 기다리고 있습니다'));
  assert.ok(!element('#app').innerHTML.includes('빈 시간 10시간'));
  assert.ok(!element('#app').innerHTML.includes('response-recommendation'));
  assert.ok(element('#app').innerHTML.includes('요청 취소'));
  // Both sides must see the analysis before the first response.
  state.user = {id:2, name:'동료',department:'개발팀'};
  await router.navigatePath('/requests/10');
  assert.ok(!element('#app').innerHTML.includes('name="keep"'));
  assert.ok(!element('#app').innerHTML.includes('id="response-comment"'));
  assert.ok(element('#app').innerHTML.includes('조건부 수락'));
  for (const decision of ['ACCEPT','CONDITIONAL_ACCEPT','REJECT']) {
    requestDetail.analysis.recommended_response = decision;
    await router.navigatePath('/requests/10');
    assert.equal((element('#app').innerHTML.match(/class="response-recommendation"/g)||[]).length,1);
    assert.ok(element('#app').innerHTML.includes(`class="secondary response-choice recommended" onclick="respond('CONDITIONAL_ACCEPT')"`));
    assert.ok(!element('#app').innerHTML.includes('추천 응답:'));
  }
  const labels = modules.get(path.resolve('static/js/shared/presentation.js')).namespace;
  const titledRequest = {task_content:'[시연 6] 긴급 배너 보정 · 박지훈 일정 변경 동의',original_text:'',status:'AWAITING_CONFIRMATION',awaiting_related_consent:true};
  assert.equal(labels.requestTitle(titledRequest),'긴급 배너 보정');
  assert.ok(labels.tag(titledRequest).includes('관계자 동의 대기'));
  assert.ok(labels.tag({...titledRequest,needs_recoordination:true}).includes('재조정 필요'));
  assert.equal(labels.requestTitle({task_content:'실제 업무 · 대안 선택'}),'실제 업무 · 대안 선택');
  const detailPage = modules.get(path.resolve('static/js/pages/request-detail.js')).namespace;
  const myCalendar = modules.get(path.resolve('static/js/components/my-calendar-dialog.js')).namespace;
  const detailHtmlBeforePopup = element('#app').innerHTML;
  const routeBeforePopup = location.pathname;
  const mainMonthBeforePopup = state.month;
  const scopeBeforePopup = state.scope;
  calendarRows = [{...multi,employee_id:2,is_new:false}];
  const popupEvent = element('#popup-calendar-event');
  popupEvent.dataset.scheduleId = '3';
  element('#my-calendar-body').querySelectorAll = () => [popupEvent];
  await myCalendar.openMyCalendarDialog();
  assert.equal(element('#my-calendar-dialog').open,true);
  assert.ok(element('#my-calendar-grid').innerHTML.includes('연속 작업'));
  assert.ok(calls.at(-1).url.includes('scope=my'));
  assert.equal(location.pathname,routeBeforePopup);
  assert.equal(element('#app').innerHTML,detailHtmlBeforePopup);
  await popupEvent.handlers.click();
  assert.equal(element('#schedule-dialog').open,true);
  assert.equal(element('#my-calendar-dialog').open,true);
  element('#schedule-dialog-close').handlers.click();
  assert.equal(element('#my-calendar-dialog').open,true);
  await element('#my-calendar-month').handlers.change({target:{value:'2026-12'}});
  await element('#my-calendar-next').handlers.click();
  assert.ok(calls.at(-1).url.includes('month=2027-01'));
  await element('#my-calendar-prev').handlers.click();
  assert.ok(calls.at(-1).url.includes('month=2026-12'));
  assert.equal(state.month,mainMonthBeforePopup);
  assert.equal(state.scope,scopeBeforePopup);
  calendarRows = [];
  await element('#my-calendar-next').handlers.click();
  assert.ok(element('#my-calendar-grid').innerHTML.includes('이번 달에 등록된 일정이 없습니다.'));
  element('#my-calendar-close').handlers.click();
  assert.equal(element('#my-calendar-dialog').open,false);
  assert.equal(location.pathname,routeBeforePopup);
  await myCalendar.openMyCalendarDialog();
  await router.navigatePath('/requests/received');
  assert.equal(element('#my-calendar-dialog').open,false);
  await router.navigatePath('/requests/10');
  const timeline = modules.get(path.resolve('static/js/shared/schedule-timeline.js')).namespace;
  const ranged = timeline.timelineEntries({start_at:'2026-11-02T00:00:00',end_at:'2026-11-06T18:00:00',schedules:[
    ...requestDetail.schedule_timeline.schedules,
    {id:10,title:'범위 밖',type:'WORK',start_at:'2026-11-07T09:00:00',end_at:'2026-11-07T18:00:00',status:'SCHEDULED'},
    {id:11,title:'취소 일정',type:'WORK',start_at:'2026-11-03T09:00:00',end_at:'2026-11-03T10:00:00',status:'CANCELLED'},
    {id:12,title:'오늘 완료',type:'WORK',start_at:'2026-11-02T09:00:00',end_at:'2026-11-02T10:00:00',status:'COMPLETED'},
  ]});
  assert.deepEqual(Array.from(ranged,entry => entry.id),[8,12,9]);
  const countResponses = () => calls.filter(call => call.url === '/api/requests/10/action').length;
  context.window.confirm = () => false;
  const responsesBefore = countResponses();
  await detailPage.respond('CONDITIONAL_ACCEPT');
  assert.equal(element('#response-dialog').open,true);
  assert.ok(element('#response-dialog-body').innerHTML.includes('name="keep"'));
  assert.ok(element('#response-dialog-body').innerHTML.includes('HARD'));
  assert.ok(element('#response-dialog-body').innerHTML.includes('SOFT'));
  assert.equal(countResponses(),responsesBefore);
  checkedConditions = [];
  element('#response-comment').value = '';
  await element('#request-response-form').handlers.submit({preventDefault(){}});
  assert.equal(countResponses(),responsesBefore);
  assert.ok(element('#response-error').textContent.includes('유지 가능한 조건'));
  checkedConditions = ['deadline','quantity'];
  element('#response-comment').value = '3개까지 가능합니다.';
  failResponse = true;
  await element('#request-response-form').handlers.submit({preventDefault(){}});
  assert.equal(element('#response-dialog').open,true);
  assert.equal(element('#response-comment').value,'3개까지 가능합니다.');
  assert.equal(element('#response-error').textContent,'응답을 저장하지 못했습니다.');
  failResponse = false;
  await element('#request-response-form').handlers.submit({preventDefault(){}});
  const responseCall = calls.findLast(call => call.url === '/api/requests/10/action');
  assert.deepEqual(JSON.parse(responseCall.body).accepted_condition_keys,['deadline','quantity']);
  assert.equal(element('#response-dialog').open,true);
  assert.ok(element('#response-dialog-body').innerHTML.includes('시연 대안을 바로 생성하시겠습니까?'));
  const beforeManualGeneration = countResponses();
  element('#response-cancel').handlers.click();
  assert.equal(countResponses(),beforeManualGeneration);
  assert.equal(element('#response-dialog').open,false);
  await detailPage.respond('REJECT');
  assert.equal(element('#response-dialog').open,true);
  assert.ok(!element('#response-dialog-body').innerHTML.includes('name="keep"'));
  element('#response-comment').value = '';
  const beforeReject = countResponses();
  await element('#request-response-form').handlers.submit({preventDefault(){}});
  assert.equal(countResponses(),beforeReject);
  assert.equal(element('#response-error').textContent,'거절 사유를 입력해주세요.');
  element('#response-comment').value = '기존 일정 때문에 진행하기 어렵습니다.';
  await element('#request-response-form').handlers.submit({preventDefault(){}});
  assert.equal(JSON.parse(calls.findLast(call => call.url === '/api/requests/10/action').body).decision,'REJECT');
  assert.deepEqual(JSON.parse(calls.findLast(call => call.url === '/api/requests/10/action').body).accepted_condition_keys,[]);
  assert.equal(element('#response-dialog').open,false);
  await detailPage.respond('CONDITIONAL_ACCEPT');
  const beforeCancel = countResponses();
  element('#response-cancel').handlers.click();
  assert.equal(countResponses(),beforeCancel);
  assert.equal(element('#response-dialog').open,false);
  const priorityRadio = element('#response-dialog input[name="schedule-priority"]:checked');
  const workloadRadio = element('#response-dialog input[name="schedule-workload"]:checked');
  priorityRadio.value = '';
  workloadRadio.value = '';
  const beforeAccept = countResponses();
  await detailPage.respond('ACCEPT');
  assert.equal(element('#response-dialog').open,true);
  assert.ok(element('#response-dialog-body').innerHTML.includes('type="radio"'));
  assert.ok(!element('#response-dialog-body').innerHTML.includes(' checked'));
  await element('#request-response-form').handlers.submit({preventDefault(){}});
  assert.equal(countResponses(),beforeAccept);
  assert.ok(element('#response-error').textContent.includes('모두 선택'));
  priorityRadio.value = 'HIGH';
  workloadRadio.value = 'LOW';
  await element('#request-response-form').handlers.submit({preventDefault(){}});
  const acceptPayload = JSON.parse(calls.findLast(call => call.url === '/api/requests/10/action').body);
  assert.equal(acceptPayload.decision,'ACCEPT');
  assert.equal(acceptPayload.schedule_priority,'HIGH');
  assert.equal(acceptPayload.schedule_workload,'LOW');
  assert.equal(element('#response-dialog').open,false);
  // Conditional acceptance can generate immediately, or leave manual generation available.
  await detailPage.respond('CONDITIONAL_ACCEPT');
  element('#response-comment').value = '마감을 연장해주세요.';
  checkedConditions = ['quantity'];
  const beforeAuto = calls.length;
  await element('#request-response-form').handlers.submit({preventDefault(){}});
  assert.equal(element('#response-dialog').open,true);
  await element('#request-response-form').handlers.submit({preventDefault(){}});
  const autoActions = calls.slice(beforeAuto).filter(call => call.url === '/api/requests/10/action').map(call => JSON.parse(call.body).action);
  assert.deepEqual(autoActions,['respond','generate']);
  assert.equal(element('#response-dialog').open,false);
  context.window.confirm = () => false;

  requestDetail.request.status = 'NEGOTIATING';
  requestDetail.rounds = [{id:1,round_no:1,status:'IN_PROGRESS'}];
  requestDetail.alternatives = [1,2,3].map(id => ({id,title:`${'ABC'[id-1]}안 · 일정 조정`,a_selected:false,b_selected:false,
    plan_json:{description:'마감을 조정해 작업합니다.',specification:'1200×600px',items:[
      {assignee_id:2,quantity:1,start_at:'2026-11-06T09:00',end_at:'2026-11-06T10:00',due_at:'2026-11-06T18:00'},
      {assignee_id:2,quantity:1,start_at:'2026-11-06T10:00',end_at:'2026-11-06T11:00',due_at:'2026-11-06T18:00'},
    ],schedule_changes:[]}}));
  await detailPage.renderRequestDetail(10);
  assert.equal((element('#app').innerHTML.match(/class="proposal-select"/g)||[]).length,3);
  assert.equal((element('#app').innerHTML.match(/class="proposal-item"/g)||[]).length,3);
  assert.ok(element('#app').innerHTML.includes('class="proposal-specification"'));
  assert.ok(element('#app').innerHTML.includes('aria-pressed="false"'));
  await detailPage.toggleAlternative(1);
  assert.equal(JSON.parse(calls.findLast(call => call.url === '/api/requests/10/action').body).selected,true);
  requestDetail.alternatives[0].b_selected = true;
  await detailPage.renderRequestDetail(10);
  assert.ok(element('#app').innerHTML.includes('✓ 내가 선택한 대안'));
  await detailPage.toggleAlternative(1);
  assert.equal(JSON.parse(calls.findLast(call => call.url === '/api/requests/10/action').body).selected,false);

  for (const alternative of requestDetail.alternatives) alternative.b_selection_completed = true;
  await detailPage.renderRequestDetail(10);
  const beforeLockedClick = countResponses();
  await detailPage.toggleAlternative(1);
  assert.equal(countResponses(),beforeLockedClick);
  assert.ok(element('#app').innerHTML.includes('✓ 선택완료'));
  for (const alternative of requestDetail.alternatives) alternative.a_selection_completed = true;
  requestDetail.alternatives[0].a_selected = true;
  const userBeforeChoose = state.user;
  state.user = {...user,id:1};
  await detailPage.renderRequestDetail(10);
  assert.ok(element('#app').innerHTML.includes('최종 대안으로 지정'));
  const alerts = [];
  context.window.alert = message => alerts.push(message);
  requestDetail.alternatives[0].a_selected = false;
  requestDetail.alternatives[1].a_selected = true;
  await detailPage.renderRequestDetail(10);
  assert.equal(alerts.length,0);
  assert.equal(element('#response-dialog').open,true);
  assert.equal(element('#response-dialog-title').textContent,'재조정이 필요해요');
  assert.ok(element('#response-dialog-body').innerHTML.includes('재조정 의견을 남겨주세요'));
  assert.ok(element('#response-dialog-body').innerHTML.includes('재조정 의견 작성'));
  const beforeNoCommonSubmit = countResponses();
  await element('#request-response-form').handlers.submit({preventDefault(){}});
  assert.equal(countResponses(),beforeNoCommonSubmit);
  assert.equal(element('#response-dialog-title').textContent,'재조정 의견');
  assert.equal(element('#response-dialog').open,true);
  element('#response-dialog').close();
  await detailPage.renderRequestDetail(10);
  assert.equal(element('#response-dialog').open,false);
  state.user = userBeforeChoose;
  requestDetail.rounds[0].id = 99;
  await detailPage.renderRequestDetail(10);
  assert.equal(element('#response-dialog').open,false);
  assert.equal(alerts.length,0);
  requestDetail.rounds[0].id = 1;
  requestDetail.alternatives[1].a_selected = false;
  state.user = userBeforeChoose;
  for (const alternative of requestDetail.alternatives) {alternative.a_selection_completed=false;alternative.b_selection_completed=false;}
  requestDetail.alternatives[0].a_selected = false;
  await detailPage.renderRequestDetail(10);
  const beforeFeedbackPath = location.pathname;
  detailPage.openRenegotiate();
  assert.equal(location.pathname,beforeFeedbackPath);
  assert.equal(element('#response-dialog').open,true);
  assert.ok(element('#response-dialog-body').innerHTML.includes('원하시는 대안이 없다면, 여기 작성해주세요.'));
  element('#response-comment').value = '';
  const beforeFeedback = countResponses();
  await element('#request-response-form').handlers.submit({preventDefault(){}});
  assert.equal(countResponses(),beforeFeedback);
  assert.equal(element('#response-error').textContent,'재조정 의견을 입력해주세요.');
  element('#response-comment').value = '수량은 유지하고 마감을 연장해주세요.';
  failResponse = true;
  await element('#request-response-form').handlers.submit({preventDefault(){}});
  assert.equal(element('#response-dialog').open,true);
  assert.equal(element('#response-comment').value,'수량은 유지하고 마감을 연장해주세요.');
  failResponse = false;
  await element('#request-response-form').handlers.submit({preventDefault(){}});
  assert.equal(element('#response-dialog').open,false);
  const feedbackCalls = calls.filter(call => call.url === '/api/requests/10/action');
  const feedbackAction = JSON.parse(feedbackCalls.at(-2).body);
  assert.equal(feedbackAction.action,'renegotiate');
  assert.equal(feedbackAction.feedback,'수량은 유지하고 마감을 연장해주세요.');
  assert.equal(JSON.parse(feedbackCalls.at(-1).body).action,'generate');

  assert.ok(element('#app').innerHTML.includes('대안 모두 불가'));
  element('#all-unavailable').checked = true;
  detailPage.toggleAllUnavailable();
  assert.equal(element('#complete-selection').disabled,false);
  assert.equal(element('#all-unavailable-feedback').hidden,false);
  element('#all-unavailable-comment').value = '';
  await detailPage.completeSelection();
  assert.equal(JSON.parse(calls.findLast(call => call.url === '/api/requests/10/action').body).action,'reject_all');
  element('#all-unavailable-comment').value = '분담 없이 진행해주세요.';
  await detailPage.completeSelection();
  const unavailableCalls=calls.filter(call => call.url === '/api/requests/10/action').slice(-2).map(call=>JSON.parse(call.body));
  assert.equal(unavailableCalls[0].action,'renegotiate');
  assert.equal(unavailableCalls[0].feedback,'분담 없이 진행해주세요.');
  assert.equal(unavailableCalls[1].action,'generate');
  element('#all-unavailable').checked = false;

  await detailPage.act('complete_selection');
  assert.equal(JSON.parse(calls.findLast(call => call.url === '/api/requests/10/action').body).action,'complete_selection');
  requestDetail.result = {negotiation_id:1,status:'PENDING_CONFIRMATION',a_confirmed_at:'2026-11-03T10:00',b_confirmed_at:null};
  requestDetail.rounds[0].selected_alternative_key = '1';
  requestDetail.consents = [{id:'1_1',alternative_id:1,employee_name:'정하은',status:'WAITING'}];
  await detailPage.renderRequestDetail(10);
  assert.ok(element('#app').innerHTML.includes('선택완료'));
  assert.ok(element('#app').innerHTML.includes('관계자 동의 현황'));
  assert.ok(element('#app').innerHTML.includes('요청 전'));
  const beforeFinalSettings = countResponses();
  await detailPage.act('confirm',{alternative_id:1});
  assert.equal(countResponses(),beforeFinalSettings+1);
  assert.equal(element('#response-dialog').open,false);
  assert.equal(JSON.parse(calls.findLast(call=>call.url==='/api/requests/10/action').body).schedule_priority,undefined);

  requestDetail.result.b_confirmed_at = '2026-11-03T11:00';
  requestDetail.consents[0].status = 'PENDING';
  await detailPage.renderRequestDetail(10);
  assert.ok(element('#app').innerHTML.includes('양측 최종 확인이 완료되어 관계자에게 동의를 요청했습니다. 관계자는 동의 시 바로 등록하고, 수행자는 전원 동의 후 일정을 설정합니다.'));
  requestDetail.consents[0].status = 'APPROVED';
  requestDetail.needs_calendar_settings=true;
  await detailPage.renderRequestDetail(10);
  assert.ok(element('#app').innerHTML.includes('동의 완료'));
  await detailPage.act('calendar_settings');
  assert.equal(element('#response-dialog').open,true);
  priorityRadio.value='LOW'; workloadRadio.value='HIGH';
  await element('#request-response-form').handlers.submit({preventDefault(){}});
  assert.equal(JSON.parse(calls.findLast(call=>call.url==='/api/requests/10/action').body).action,'calendar_settings');

  const calendarActor=state.user;
  state.user={...state.user,id:requestDetail.request.requester_id};
  await detailPage.renderRequestDetail(10);
  assert.ok(element('#app').innerHTML.includes('요청자는 일정 등록 대상이 아니므로'));
  assert.ok(!element('#app').innerHTML.includes('onclick="act(\'calendar_settings\')"'));
  await detailPage.act('confirm',{alternative_id:1});
  assert.equal(element('#response-dialog').open,false);
  assert.equal(JSON.parse(calls.findLast(call=>call.url==='/api/requests/10/action').body).schedule_priority,undefined);
  state.user=calendarActor;

  state.consents = [{id:'1_1',request_title:'뉴스레터 이미지 업무 분담',alternative_title:'A안 · 업무 분담',description:'A안 · 업무 분담 · 정하은 님의 업무 분담이 필요합니다.',status:'PENDING'}];
  await router.navigatePath('/requests/consents');
  assert.equal(state.page,'consents');
  assert.equal(element('#breadcrumb').textContent,'협업 요청함 / 관계자 동의 요청');
  assert.ok(element('#app').innerHTML.includes('<strong>뉴스레터 이미지 업무 분담</strong>'));
  assert.ok(!element('#app').innerHTML.includes('A안 · 업무 분담'));
  assert.ok(element('#app').innerHTML.includes('협업 상세 보기'));
  const inboxPage = modules.get(path.resolve('static/js/pages/inbox.js')).namespace;
  consentDetails = {request:{...requestDetail.request,request_message:'상세 협업 요청 본문',requester_name:'김민지',assignee_name:'이서준'},
    consent:{id:'1_1',status:'PENDING'},alternative:requestDetail.alternatives[0],
    confirmation:{a_confirmed_at:'2026-11-03T10:00',b_confirmed_at:'2026-11-03T11:00'},response:{assignee_comment:'규격을 유지합니다.'}};
  const consentPanel = {open:true,dataset:{},isConnected:true};
  await inboxPage.loadConsentDetail('1_1',consentPanel);
  assert.ok(element('#consent-detail-1_1').innerHTML.includes('상세 협업 요청 본문'));
  assert.ok(element('#consent-detail-1_1').innerHTML.includes('김민지'));
  assert.ok(element('#consent-detail-1_1').innerHTML.includes('이서준'));
  assert.ok(element('#consent-detail-1_1').innerHTML.includes('내 동의가 필요한 내용'));
  assert.ok(element('#consent-detail-1_1').innerHTML.includes('양측이 최종 확인한 대안'));
  assert.ok(element('#consent-detail-1_1').innerHTML.includes('HARD'));
  assert.ok(element('#consent-detail-1_1').innerHTML.includes("answerConsent('1_1','APPROVED')"));
  const loadedCalls = calls.length;
  await inboxPage.loadConsentDetail('1_1',consentPanel);
  assert.equal(calls.length,loadedCalls);
  failConsentDetail = true;
  await inboxPage.loadConsentDetail('1_1',{open:true,dataset:{},isConnected:true});
  assert.ok(element('#consent-detail-1_1').innerHTML.includes('본인에게 전달된 동의 요청만 확인'));
  assert.ok(!element('#consent-detail-1_1').innerHTML.includes('상세 협업 요청 본문'));
  failConsentDetail = false;


  const beforeConsentSettings = calls.length;
  await inboxPage.answerConsent('1_1','APPROVED');
  assert.equal(calls.length,beforeConsentSettings);
  assert.equal(element('#response-dialog').open,true);
  assert.ok(element('#response-dialog-title').textContent.includes('관계자 동의'));
  priorityRadio.value='HIGH'; workloadRadio.value='LOW';
  await element('#request-response-form').handlers.submit({preventDefault(){}});
  const consentApproval=JSON.parse(calls.findLast(call=>call.url==='/api/consents/1_1' && call.method==='POST').body);
  assert.equal(consentApproval.status,'APPROVED');
  assert.equal(consentApproval.schedule_priority,'HIGH');
  assert.equal(consentApproval.schedule_workload,'LOW');
  assert.equal(element('#response-dialog').open,false);
  inboxPage.configureConsentCalendar('1_1');
  assert.equal(element('#response-dialog').open,true);
  assert.ok(element('#response-dialog-body').innerHTML.includes('schedule-workload'));
  priorityRadio.value='MEDIUM'; workloadRadio.value='LOW';
  await element('#request-response-form').handlers.submit({preventDefault(){}});
  const relatedSettings = JSON.parse(calls.findLast(call=>call.url==='/api/consents/1_1/calendar-settings').body);
  assert.equal(relatedSettings.schedule_priority,'MEDIUM');
  assert.equal(relatedSettings.schedule_workload,'LOW');
  const beforeRefusal = calls.length;
  inboxPage.answerConsent('1_1','REJECTED');
  assert.equal(calls.length,beforeRefusal);
  assert.equal(element('#response-dialog').open,true);
  assert.ok(element('#response-dialog-body').innerHTML.includes('거부 사유는 요청자와 수행자에게 전달'));
  element('#response-comment').value = '';
  await element('#request-response-form').handlers.submit({preventDefault(){}});
  assert.equal(calls.length,beforeRefusal);
  element('#response-comment').value = '업무량이 많아 이번 분담은 어렵습니다.';
  failConsentReply = true;
  await element('#request-response-form').handlers.submit({preventDefault(){}});
  assert.equal(element('#response-dialog').open,true);
  assert.equal(element('#response-comment').value,'업무량이 많아 이번 분담은 어렵습니다.');
  failConsentReply = false;
  await element('#request-response-form').handlers.submit({preventDefault(){}});
  const refusalCall = calls.findLast(call => call.url === '/api/consents/1_1' && call.body);
  assert.deepEqual(JSON.parse(refusalCall.body),{status:'REJECTED',reason:'업무량이 많아 이번 분담은 어렵습니다.'});
  assert.equal(element('#response-dialog').open,false);

  requestDetail.request.needs_recoordination = true;
  requestDetail.request.consent_rejections = [{employee_id:4,employee_name:'정하은',reason:'업무량이 많아 분담하기 어렵습니다.'}];
  requestDetail.consents[0].status = 'REJECTED';
  await router.navigatePath('/requests/10');
  assert.ok(element('#app').innerHTML.includes('관계자 동의 거부 · 재조정 필요'));
  assert.ok(element('#app').innerHTML.includes('정하은 님이 동의를 거부했습니다.'));
  assert.ok(element('#app').innerHTML.includes('업무량이 많아 분담하기 어렵습니다.'));
  const beforeBlockedSelect = calls.length;
  await detailPage.toggleAlternative(1);
  assert.equal(calls.length,beforeBlockedSelect);
  state.requests = [{...requestDetail.request,status:'AWAITING_CONFIRMATION'}];
  await router.navigatePath('/requests/received');
  assert.ok(element('#app').innerHTML.includes('recoordination-badge'));
  assert.ok(element('#app').innerHTML.includes('재조정 필요'));
  await router.navigatePath('/requests/10');
  simulateRecoordination = true;
  failGeneration = true;
  const toastBeforeGeneration=element('#toast').textContent;
  const beforeRestart = calls.length;
  await detailPage.restartAfterRejection();
  const restartActions = calls.slice(beforeRestart).filter(call => call.url === '/api/requests/10/action').map(call => JSON.parse(call.body));
  assert.equal(restartActions[0].action,'restart_after_rejection');
  assert.equal(restartActions[0].source_round_id,1);
  assert.equal(restartActions[1].action,'generate');
  assert.ok(element('#app').innerHTML.includes('관계자 거부 의견을 반영해 재조정 중입니다.'));
  assert.ok(element('#app').innerHTML.includes('대안 생성'));
  assert.equal(state.activeDetail.request.needs_recoordination,false);
  assert.ok(element('#app').innerHTML.includes('alternative-error'));
  assert.ok(element('#app').innerHTML.includes('AI 생성에 실패했습니다.'));
  assert.ok(!element('#toast').textContent.includes('AI 생성에 실패했습니다.'));
  await detailPage.renderRequestDetail(10);
  assert.ok(element('#app').innerHTML.includes('alternative-error'));
  failGeneration = false;
  simulateRecoordination = false;

  state.requests=[{...requestDetail.request,is_new:true,notice_version:'a'.repeat(64)}];
  state.consents=[{id:'1_1',request_id:10,is_new:true,notice_version:'b'.repeat(64)}];
  router.syncNav();
  assert.equal(element('#received-new-badge').hidden,false);
  assert.equal(element('#consents-new-badge').hidden,false);
  assert.equal(element('#requests-new-badge').hidden,false);
  requestDetail.notice_version='a'.repeat(64);
  await router.navigatePath('/requests/10');
  assert.equal(state.requests[0].is_new,false);
  assert.equal(element('#received-new-badge').hidden,true);
  assert.equal(element('#requests-new-badge').hidden,false);
  delete requestDetail.notice_version;
  consentDetails.notice_version='b'.repeat(64);
  await router.navigatePath('/requests/consents');
  await inboxPage.loadConsentDetail('1_1',{open:true,dataset:{},isConnected:true});
  assert.equal(state.consents[0].is_new,false);
  assert.equal(element('#consents-new-badge').hidden,true);
  assert.equal(element('#requests-new-badge').hidden,true);
  delete consentDetails.notice_version;
  newScheduleCount = 2;
  await router.refreshData(false);
  assert.equal(element('#schedule-new-badge').hidden,false);
  assert.equal(element('#schedule-new-badge').title,'새 일정 2건');
  calendarRows = [{id:3,employee_id:2,employee_name:'동료',type:'WORK',title:'새 협업 일정',start_at:'2026-11-06T09:00:00',end_at:'2026-11-06T10:00:00',is_new:true}];
  state.month = '2026-11';
  const readsBeforeCalendar=calls.filter(call=>call.url==='/api/schedules/notifications/read').length;
  await router.navigatePath('/calendar/my');
  assert.equal(calls.filter(call=>call.url==='/api/schedules/notifications/read').length,readsBeforeCalendar);
  assert.ok(element('#calendar-body').innerHTML.includes('schedule-unread'));
  assert.equal(element('#schedule-new-badge').hidden,false);
  scheduleDetailIsNew=true; scheduleDetailOwner=2;
  const removals=[];
  clickedScheduleButtons=[{classList:{remove:name=>removals.push(name)}},{classList:{remove:name=>removals.push(name)}}];
  await calendar.openSchedule({id:3});
  const readCall = calls.findLast(call => call.url === '/api/schedules/notifications/read');
  assert.deepEqual(JSON.parse(readCall.body).schedule_ids,[3]);
  assert.deepEqual(removals,['schedule-unread','schedule-unread']);
  assert.equal(state.newScheduleCount,1);
  assert.equal(element('#schedule-new-badge').hidden,false);
  scheduleDetailIsNew=false;
  clickedScheduleButtons=[];
  element('#schedule-dialog-close').handlers.click();
  calendarRows = [];
  const auth = modules.get(path.resolve('static/js/pages/auth.js')).namespace;
  await auth.logout();
  assert.equal(state.user, null);
  assert.equal(element('#profile-login-id').textContent, '');
  assert.equal(element('#profile-status').hidden, true);
  state.user = user;
  element('#profile-login-id').textContent = 'tester';
  expired = true;
  const client = modules.get(path.resolve('static/js/core/api.js')).namespace;
  await assert.rejects(() => client.api('/requests'), /로그인이 만료/);
  assert.equal(state.user, null);
  assert.equal(element('#profile-login-id').textContent, '');
  assert.equal(element('#profile-status').hidden, true);
  await router.navigatePath('/calendar/my');
  assert.equal(location.pathname, '/login');
  assert.equal(state.loginDestination, '/calendar/my');
  assert.ok(element('#auth-root').innerHTML.includes('auth-form'));
  assert.equal(typeof context.window.fillDemo, 'function');
  assert.deepEqual(errors, []);
  console.log(`Frontend smoke checks passed (${modules.size} ES modules, startup, navigation, auth, template actions).`);
})().catch(error => { console.error(error); process.exitCode = 1; });
