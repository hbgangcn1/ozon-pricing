import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import RegisterPage from '../pages/RegisterPage';
import { authAPI } from '../services/api';
import { useAuthStore } from '../stores/authStore';
import { toast } from 'sonner';

vi.mock('../services/api', () => ({
  authAPI: {
    register: vi.fn(),
    checkUsername: vi.fn().mockResolvedValue({ available: true, reason: null }),
    getSecurityQuestions: vi.fn().mockResolvedValue({
      data: {
        questions: [
          '您母亲的姓氏是什么？',
          '您父亲的名字是什么？',
          '您就读的小学名称是什么？',
          '您最喜欢的宠物名字是什么？',
          '您配偶的名字是什么？',
        ],
      },
    }),
  },
  settingsAPI: {
    get: vi.fn().mockResolvedValue({ open_registration: true }),
  },
}));

vi.mock('../stores/authStore', () => ({
  useAuthStore: vi.fn(),
}));

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));


describe('RegisterPage', () => {
  const mockSetAuth = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.mockReturnValue({ setAuth: mockSetAuth });
  });

  const renderComponent = () =>
    render(
      <MemoryRouter>
        <RegisterPage />
      </MemoryRouter>
    );

  it('renders registration form with all fields', () => {
    renderComponent();
    expect(screen.getByPlaceholderText(/请输入用户名/)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/13位以上/)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/请再次输入密码/)).toBeInTheDocument();
    expect(screen.getByRole('combobox')).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/请输入安全答案/)).toBeInTheDocument();
  });

  it('shows "物流定价系统" heading and "创建新账户" subtitle', () => {
    renderComponent();
    expect(screen.getByText('物流定价系统')).toBeInTheDocument();
    expect(screen.getByText('创建新账户')).toBeInTheDocument();
  });

  it('shows "立即登录" link', () => {
    renderComponent();
    expect(screen.getByText('立即登录')).toBeInTheDocument();
    expect(screen.getByText('立即登录').closest('a')).toHaveAttribute('href', '/login');
  });

  it('validates username min length (3)', async () => {
    renderComponent();
    fireEvent.change(screen.getByPlaceholderText(/请输入用户名/), { target: { value: 'ab' } });
    fireEvent.click(screen.getByRole('button', { name: '注册' }));
    
    await waitFor(() => {
      expect(screen.getByText('用户名至少3位')).toBeInTheDocument();
    });
  });

  it('validates password requirements (min 13, regex for complexity)', async () => {
    renderComponent();
    fireEvent.change(screen.getByPlaceholderText(/13位以上/), { target: { value: 'short' } });
    fireEvent.click(screen.getByRole('button', { name: '注册' }));
    
    await waitFor(() => {
      expect(screen.getByText('密码至少13位')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText(/13位以上/), { target: { value: 'thisislongenoughbutnocapitalornumbers' } });
    fireEvent.click(screen.getByRole('button', { name: '注册' }));
    
    await waitFor(() => {
      expect(screen.getByText('密码必须包含大小写字母、数字和特殊字符')).toBeInTheDocument();
    });
  });

  it('shows "两次密码不一致" when passwords don\'t match', async () => {
    renderComponent();
    fireEvent.change(screen.getByPlaceholderText(/13位以上/), { target: { value: 'ValidPassword123!' } });
    fireEvent.change(screen.getByPlaceholderText(/请再次输入密码/), { target: { value: 'ValidPassword123@' } });
    fireEvent.click(screen.getByRole('button', { name: '注册' }));
    
    await waitFor(() => {
      expect(screen.getByText('两次密码不一致')).toBeInTheDocument();
    });
  });

  it('calls authAPI.register and setAuth + navigates on success', async () => {
    renderComponent();
    
    const mockResponse = { access_token: 'token123', user: { id: 1, username: 'validuser' } };
    authAPI.register.mockResolvedValueOnce(mockResponse);

    fireEvent.change(screen.getByPlaceholderText(/请输入用户名/), { target: { value: 'validuser' } });
    fireEvent.change(screen.getByPlaceholderText(/13位以上/), { target: { value: 'ValidPassword123!' } });
    fireEvent.change(screen.getByPlaceholderText(/请再次输入密码/), { target: { value: 'ValidPassword123!' } });
    fireEvent.change(screen.getByRole('combobox'), { target: { value: '您母亲的姓氏是什么？' } });
    fireEvent.change(screen.getByPlaceholderText(/请输入安全答案/), { target: { value: 'answer' } });
    

    fireEvent.click(screen.getByRole('button', { name: '注册' }));

    await waitFor(() => {
      expect(authAPI.register).toHaveBeenCalledWith({
        username: 'validuser',
        password: 'ValidPassword123!',
        security_question: '您母亲的姓氏是什么？',
        security_answer: 'answer',
      });
      expect(mockSetAuth).toHaveBeenCalledWith(mockResponse.user, mockResponse.access_token);
      expect(toast.success).toHaveBeenCalledWith('注册成功');
      expect(mockNavigate).toHaveBeenCalledWith('/pricing');
    });
  });

  it('shows error on registration failure', async () => {
    renderComponent();
    
    authAPI.register.mockRejectedValueOnce({ response: { data: { detail: '用户名已存在' } } });

    fireEvent.change(screen.getByPlaceholderText(/请输入用户名/), { target: { value: 'validuser' } });
    fireEvent.change(screen.getByPlaceholderText(/13位以上/), { target: { value: 'ValidPassword123!' } });
    fireEvent.change(screen.getByPlaceholderText(/请再次输入密码/), { target: { value: 'ValidPassword123!' } });
    fireEvent.change(screen.getByRole('combobox'), { target: { value: '您母亲的姓氏是什么？' } });
    fireEvent.change(screen.getByPlaceholderText(/请输入安全答案/), { target: { value: 'answer' } });
    

    fireEvent.click(screen.getByRole('button', { name: '注册' }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('用户名已存在');
    });
  });

  it('renders password strength indicator when password is typed', async () => {
    renderComponent();

    fireEvent.change(screen.getByPlaceholderText(/13位以上/), {
      target: { value: 'weakpass' },
    });

    await waitFor(() => {
      expect(screen.getByTestId('password-strength')).toBeInTheDocument();
      expect(screen.getByTestId('password-strength-label')).toBeInTheDocument();
    });
  });

  it('blocks submit and shows error when username is taken', async () => {
    authAPI.checkUsername.mockResolvedValueOnce({
      available: false,
      reason: '用户名已被占用',
    });

    renderComponent();

    fireEvent.change(screen.getByPlaceholderText(/请输入用户名/), {
      target: { value: 'takenuser' },
    });

    await waitFor(
      () => {
        expect(screen.getByTestId('username-taken')).toBeInTheDocument();
        expect(screen.getByTestId('username-taken-msg')).toHaveTextContent('用户名已被占用');
      },
      { timeout: 2000 }
    );

    fireEvent.change(screen.getByPlaceholderText(/13位以上/), {
      target: { value: 'ValidPassword123!' },
    });
    fireEvent.change(screen.getByPlaceholderText(/请再次输入密码/), {
      target: { value: 'ValidPassword123!' },
    });
    fireEvent.change(screen.getByRole('combobox'), {
      target: { value: '您母亲的姓氏是什么？' },
    });
    fireEvent.change(screen.getByPlaceholderText(/请输入安全答案/), {
      target: { value: 'answer' },
    });

    fireEvent.click(screen.getByRole('button', { name: '注册' }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('用户名已被占用');
    });
    expect(authAPI.register).not.toHaveBeenCalled();
  });

  it('debounces username checks to fire once across rapid input changes', async () => {
    vi.useFakeTimers();
    try {
      renderComponent();
      authAPI.checkUsername.mockClear();

      const usernameInput = screen.getByPlaceholderText(/请输入用户名/);
      fireEvent.change(usernameInput, { target: { value: 'abc' } });
      fireEvent.change(usernameInput, { target: { value: 'abcd' } });
      fireEvent.change(usernameInput, { target: { value: 'abcde' } });

      vi.advanceTimersByTime(399);
      expect(authAPI.checkUsername).not.toHaveBeenCalled();

      vi.advanceTimersByTime(2);
      expect(authAPI.checkUsername).toHaveBeenCalledTimes(1);
      expect(authAPI.checkUsername).toHaveBeenCalledWith('abcde');
    } finally {
      vi.useRealTimers();
    }
  });

  it('submit button shows "注册中..." when loading', async () => {
    renderComponent();
    
    authAPI.register.mockImplementationOnce(() => new Promise((resolve) => setTimeout(resolve, 100)));

    fireEvent.change(screen.getByPlaceholderText(/请输入用户名/), { target: { value: 'validuser' } });
    fireEvent.change(screen.getByPlaceholderText(/13位以上/), { target: { value: 'ValidPassword123!' } });
    fireEvent.change(screen.getByPlaceholderText(/请再次输入密码/), { target: { value: 'ValidPassword123!' } });
    fireEvent.change(screen.getByRole('combobox'), { target: { value: '您母亲的姓氏是什么？' } });
    fireEvent.change(screen.getByPlaceholderText(/请输入安全答案/), { target: { value: 'answer' } });
    

    fireEvent.click(screen.getByRole('button', { name: '注册' }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '注册中...' })).toBeInTheDocument();
    });
  });

});
