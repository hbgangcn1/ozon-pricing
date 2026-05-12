import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { Select, SelectTrigger, SelectValue } from '../../components/ui/select';

describe('SelectTrigger component', () => {
  it('applies error styling classes', () => {
    render(
      <Select>
        <SelectTrigger data-testid="test-select" aria-invalid="true">
          <SelectValue placeholder="Select an option" />
        </SelectTrigger>
      </Select>
    );
    const trigger = screen.getByTestId('test-select');
    
    expect(trigger.getAttribute('aria-invalid')).toBe('true');
    expect(trigger.className).toContain('aria-[invalid=true]:border-status-error');
    expect(trigger.className).toContain('aria-[invalid=true]:ring-status-error');
  });

  it('passes aria-describedby to the DOM element', () => {
    render(
      <Select>
        <SelectTrigger data-testid="test-select" aria-describedby="error-message">
          <SelectValue placeholder="Select an option" />
        </SelectTrigger>
      </Select>
    );
    const trigger = screen.getByTestId('test-select');
    expect(trigger.getAttribute('aria-describedby')).toBe('error-message');
  });
});
