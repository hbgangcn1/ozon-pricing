/**
 * JSDOM CSS Resolution Strategy: Strategy B (Precompile Tailwind CSS and inject into JSDOM)
 * 
 * Reason: `vitest.config.js` sets `css: false`, which means external stylesheets are completely 
 * ignored by the test runner. By manually running the Tailwind CSS CLI during `beforeAll` and 
 * appending the raw CSS text via a `<style>` block into `document.head`, we force JSDOM to 
 * parse the CSS rules. This allows `window.getComputedStyle` to return actual computed values 
 * applied by Tailwind utility classes (e.g. `bg-muted`), enabling a realistic test of the 
 * visual styles instead of merely checking class names.
 */

import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { render, screen } from '@testing-library/react';
import { execSync } from 'child_process';
import { VirtualTable } from '@/components/ui/virtual-table';
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from '@/components/ui/table';

describe('Table Header Opacity', () => {
  let styleElement;

  // P3: Tailwind CLI cold start under parallel Vitest load on Windows
  // can exceed the default 10s hookTimeout. 60s gives ample headroom.
  beforeAll(() => {
    // Synchronously compile Tailwind CSS for the UI elements
    // We run this from the process.cwd() (which should be the frontend folder in vitest)
    const cssOutput = execSync(
      'npx tailwindcss -i src/styles/globals.css --minify',
      { encoding: 'utf-8' }
    );

    // Inject the compiled CSS into JSDOM
    styleElement = document.createElement('style');
    styleElement.innerHTML = cssOutput;
    document.head.appendChild(styleElement);
  }, 60_000);

  afterAll(() => {
    if (styleElement) {
      document.head.removeChild(styleElement);
    }
  });

  it('VirtualTable header is not transparent', () => {
    const items = [{ id: 1, name: 'Item 1' }];
    const columns = [
      { key: 'name', header: 'Name', width: '100px', render: (item) => item.name }
    ];

    render(
      <VirtualTable 
        items={items} 
        columns={columns} 
        getItemKey={(item) => item.id} 
      />
    );

    // The data-testid "virtual-table-header" is set on the header container
    const header = screen.getByTestId('virtual-table-header');
    const computedStyle = window.getComputedStyle(header);
    const bg = computedStyle.backgroundColor;
    
    // In JSDOM, missing/transparent backgrounds evaluate to '' or 'rgba(0, 0, 0, 0)' or 'transparent'
    const isTransparent = bg === '' || bg === 'rgba(0, 0, 0, 0)' || bg === 'transparent';
    expect(isTransparent).toBe(false);
    expect(bg).toContain('hsl'); // Typically parses as 'hsl(var(--muted))' or actual RGB if variables resolved (though CSS vars in JSDOM sometimes stay as written unless resolved)
  });

  it('shadcn TableHeader is not transparent', () => {
    render(
      <Table>
        <TableHeader data-testid="shadcn-table-header">
          <TableRow>
            <TableHead>Column 1</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow>
            <TableCell>Data 1</TableCell>
          </TableRow>
        </TableBody>
      </Table>
    );

    const header = screen.getByTestId('shadcn-table-header');
    const computedStyle = window.getComputedStyle(header);
    const bg = computedStyle.backgroundColor;

    const isTransparent = bg === '' || bg === 'rgba(0, 0, 0, 0)' || bg === 'transparent';
    expect(isTransparent).toBe(false);
  });

  it('negative control: non-existent tailwind class should be transparent', () => {
    // This control proves that our test isn't just mindlessly passing everything.
    // A missing class means the CSS rule doesn't exist in the injected style element.
    render(<div data-testid="negative-control" className="bg-doesnotexist">Control</div>);

    const control = screen.getByTestId('negative-control');
    const computedStyle = window.getComputedStyle(control);
    const bg = computedStyle.backgroundColor;

    const isTransparent = bg === '' || bg === 'rgba(0, 0, 0, 0)' || bg === 'transparent';
    expect(isTransparent).toBe(true);
  });
});
