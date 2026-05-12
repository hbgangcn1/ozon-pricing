import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { Input } from '../../components/ui/input';

describe('Input component', () => {
  it('applies error styling classes', () => {
    render(<Input data-testid="test-input" aria-invalid="true" />);
    const input = screen.getByTestId('test-input');
    
    expect(input.getAttribute('aria-invalid')).toBe('true');
    expect(input.className).toContain('aria-[invalid=true]:border-status-error');
    expect(input.className).toContain('aria-[invalid=true]:ring-status-error');
  });

  it('passes aria-describedby to the DOM element', () => {
    render(<Input data-testid="test-input" aria-describedby="error-message" />);
    const input = screen.getByTestId('test-input');
    expect(input.getAttribute('aria-describedby')).toBe('error-message');
  });
});
