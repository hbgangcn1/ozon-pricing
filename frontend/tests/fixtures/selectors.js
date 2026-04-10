export const LOGIN_PAGE = {
  usernameInput: 'input[name="username"]',
  passwordInput: 'input[name="password"]',
  submitButton: 'button[type="submit"]',
  heading: '物流定价系统',
};

export const REGISTER_PAGE = {
  usernameInput: 'input[name="username"]',
  passwordInput: 'input[name="password"]',
  confirmPasswordInput: 'input[name="confirmPassword"]',
  securityQuestionSelect: '#security_question',
  securityAnswerInput: 'input[name="security_answer"]',
  eulaCheckbox: 'button[role="checkbox"]',
  submitButton: 'button[type="submit"]',
};

export const LOGISTICS_PAGE = {
  nameInput: '#modal-name',
  typeCombobox: '[role="combobox"]',
  dialog: '[role="dialog"]',
  addButton: 'button:has-text("添加物流规则")',
  table: 'table',
  tableRow: 'table tbody tr',
};

export const ACCOUNT_PAGE = {
  currentPasswordInput: 'input[name="current_password"]',
  newPasswordInput: 'input[name="new_password"]',
  confirmPasswordInput: 'input[name="confirm_password"]',
  submitButton: 'button[type="submit"]',
  form: 'form',
};

export const NAV = {
  userMenu: '[data-testid="user-menu"], button[aria-haspopup="menu"]',
  logoutButton: 'text=退出登录',
};
