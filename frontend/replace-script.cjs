const fs = require('fs');
const path = require('path');

const dir = 'src/components/ui';
const files = fs.readdirSync(dir).filter(f => f.endsWith('.jsx') || f.endsWith('.tsx'));

const exactMappings = {
  // Border
  'border-zinc-800': 'border-surface-high',
  'border-zinc-700': 'border-surface-highest',
  'border-zinc-200': 'border-surface-high', // just in case
  // Background
  'bg-zinc-950': 'bg-surface',
  'bg-zinc-900': 'bg-surface-container',
  'bg-zinc-800': 'bg-surface-high',
  'bg-indigo-500': 'bg-primary',
  'bg-red-500': 'bg-status-error',
  // Text
  'text-zinc-50': 'text-text-primary',
  'text-zinc-400': 'text-text-secondary',
  'text-zinc-500': 'text-text-muted',
  'text-red-500': 'text-status-error', // catching red
  'placeholder:text-zinc-500': 'placeholder:text-text-muted',
  'placeholder:text-zinc-400': 'placeholder:text-text-muted',
  // Hover
  'hover:bg-indigo-600': 'hover:bg-primary/85',
  'hover:bg-zinc-700': 'hover:bg-surface-highest',
  'hover:bg-red-600': 'hover:bg-status-error/85',
  'hover:text-zinc-50': 'hover:text-text-primary',
  'hover:text-zinc-900': 'hover:text-text-primary',
  // Focus
  'ring-offset-zinc-950': 'ring-offset-surface',
  'focus-visible:ring-zinc-950': 'focus-visible:ring-primary',
  'focus-visible:ring-zinc-800': 'focus-visible:ring-primary',
  'focus-visible:ring-indigo-500': 'focus-visible:ring-primary',
  'focus:ring-indigo-500': 'focus:ring-primary',
  'focus:bg-zinc-900': 'focus:bg-surface-container',
  // Data attributes
  'data-[state=checked]:bg-indigo-500': 'data-[state=checked]:bg-primary',
  'data-[state=unchecked]:bg-zinc-800': 'data-[state=unchecked]:bg-surface-high',
  'data-[state=active]:bg-zinc-950': 'data-[state=active]:bg-surface',
  'data-[state=active]:text-zinc-50': 'data-[state=active]:text-text-primary',
  'data-[state=checked]:text-zinc-50': 'data-[state=checked]:text-text-primary',
  'data-[state=checked]:text-zinc-900': 'data-[state=checked]:text-text-primary',
};

// More generic fallbacks (runs after exact mappings)
const fallbacks = [
  { regex: /\b([a-z:]*)-zinc-950\b/g, replace: '$1-surface' },
  { regex: /\b([a-z:]*)-zinc-900\b/g, replace: '$1-surface-container' },
  { regex: /\b([a-z:]*)-zinc-800\b/g, replace: '$1-surface-high' },
  { regex: /\b([a-z:]*)-zinc-700\b/g, replace: '$1-surface-highest' },
  { regex: /\b([a-z:]*)-zinc-600\b/g, replace: '$1-surface-bright' },
  { regex: /\btext-zinc-300\b/g, replace: 'text-text-secondary' },
  { regex: /\btext-zinc-200\b/g, replace: 'text-text-secondary' },
  { regex: /\btext-zinc-100\b/g, replace: 'text-text-primary' },
  { regex: /\b([a-z:]*)-zinc-500\b/g, replace: '$1-text-muted' },
  { regex: /\b([a-z:]*)-zinc-400\b/g, replace: '$1-text-secondary' },
  { regex: /\b([a-z:]*)-zinc-50\b/g, replace: '$1-text-primary' },
  { regex: /\b([a-z:]*)-indigo-500\b/g, replace: '$1-primary' },
  { regex: /\b([a-z:]*)-indigo-600\b/g, replace: '$1-primary/85' },
  { regex: /\b([a-z:]*)-red-500\b/g, replace: '$1-status-error' },
  { regex: /\b([a-z:]*)-red-600\b/g, replace: '$1-status-error/85' },
];

let changedCount = 0;
for (const file of files) {
  const filePath = path.join(dir, file);
  let content = fs.readFileSync(filePath, 'utf8');
  let original = content;

  // Split on whitespace or quotes to match exact classes safely
  // Actually, string replace with RegExp boundary is safer
  for (const [key, value] of Object.entries(exactMappings)) {
    // Escape brackets for regex
    const escapedKey = key.replace(/\[/g, '\\[').replace(/\]/g, '\\]');
    // Using positive lookbehind/lookahead for word boundaries including '-' and ':'
    const regex = new RegExp(`(?<=[\\s"'\`])` + escapedKey + `(?=[\\s"'\`])`, 'g');
    content = content.replace(regex, value);
  }

  // Fallbacks
  for (const { regex, replace } of fallbacks) {
    content = content.replace(regex, replace);
  }

  if (content !== original) {
    fs.writeFileSync(filePath, content, 'utf8');
    console.log(`Updated ${file}`);
    changedCount++;
  }
}
console.log(`Processed ${files.length} files. Changed ${changedCount} files.`);
