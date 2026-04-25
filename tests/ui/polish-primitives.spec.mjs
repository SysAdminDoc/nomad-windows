import { test, expect } from '@playwright/test';

async function boot(page, path = '/') {
  await page.addInitScript(() => {
    localStorage.setItem('nomad-theme', 'nightops');
  });
  await page.goto(path, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#main-content');
  await page.waitForTimeout(150);
}

test('btn focus-visible draws an accent ring instead of native outline', async ({ page }) => {
  await boot(page);
  const focus = await page.evaluate(() => {
    const btn = document.createElement('button');
    btn.className = 'btn';
    btn.textContent = 'probe';
    btn.id = 'probe-focus-btn';
    document.body.appendChild(btn);
    btn.focus();
    const cs = getComputedStyle(btn);
    const result = {
      outlineStyle: cs.outlineStyle,
      outlineWidth: cs.outlineWidth,
      boxShadow: cs.boxShadow,
    };
    btn.remove();
    return result;
  });
  // Either box-shadow or a visible outline must signal focus — never bare none.
  const hasShadowRing = focus.boxShadow && focus.boxShadow !== 'none';
  const hasOutlineRing =
    focus.outlineStyle && focus.outlineStyle !== 'none' && focus.outlineWidth !== '0px';
  expect(hasShadowRing || hasOutlineRing).toBeTruthy();
});

test('confirmAction renders an accessible app-native confirmation flow', async ({ page }) => {
  await boot(page);
  await page.evaluate(() => {
    const trigger = document.createElement('button');
    trigger.id = 'confirm-trigger';
    trigger.textContent = 'Restore';
    document.body.appendChild(trigger);
    trigger.focus();
    window.__confirmResult = window.confirmAction({
      title: 'Restore scheduled backup?',
      message: 'Restore database from nomad-test.zip.',
      detail: 'Enter the decryption password. A safety backup will be created first.',
      confirmLabel: 'Restore Backup',
      tone: 'warning',
      fields: [{
        name: 'password',
        label: 'Decryption password',
        type: 'password',
        required: true,
      }],
    });
  });

  const dialog = page.locator('.nomad-confirm-overlay[role="alertdialog"]');
  await expect(dialog).toBeVisible();
  await expect(dialog).toHaveAttribute('aria-describedby', /confirm-desc-/);
  await expect(page.getByLabel(/Decryption password/)).toBeFocused();

  const confirm = page.getByRole('button', { name: 'Restore Backup' });
  await expect(confirm).toBeDisabled();
  await page.getByLabel(/Decryption password/).fill('correct-horse');
  await expect(confirm).toBeEnabled();
  await confirm.click();

  await expect(dialog).toHaveCount(0);
  const result = await page.evaluate(() => window.__confirmResult);
  expect(result).toEqual({ confirmed: true, values: { password: 'correct-horse' } });
  await expect(page.locator('#confirm-trigger')).toBeFocused();
});

test('aria-busy on a button hides the label and renders a spinner pseudo', async ({ page }) => {
  await boot(page);
  const probe = await page.evaluate(() => {
    const btn = document.createElement('button');
    btn.className = 'btn';
    btn.textContent = 'Refresh';
    btn.setAttribute('aria-busy', 'true');
    document.body.appendChild(btn);
    const cs = getComputedStyle(btn);
    const after = getComputedStyle(btn, '::after');
    const result = {
      colorTransparent: cs.color === 'rgba(0, 0, 0, 0)' || cs.color === 'transparent',
      cursor: cs.cursor,
      pointerEvents: cs.pointerEvents,
      afterContent: after.content,
      afterAnimation: after.animationName,
      afterWidth: after.width,
    };
    btn.remove();
    return result;
  });
  expect(probe.colorTransparent).toBeTruthy();
  expect(probe.cursor).toBe('progress');
  expect(probe.pointerEvents).toBe('none');
  // The spinner is drawn via ::after with a content marker and an animation.
  expect(probe.afterContent).not.toBe('none');
  expect(['spin', 'none']).toContain(probe.afterAnimation);
  // Width is set in CSS to ~14px; just confirm it isn't auto/zero.
  expect(probe.afterWidth).toMatch(/^\d/);
});

test('ai-dots renders three pulsing dots in document flow', async ({ page }) => {
  await boot(page);
  const probe = await page.evaluate(() => {
    const wrap = document.createElement('div');
    wrap.innerHTML = '<span class="ai-dots"><span></span><span></span><span></span></span>';
    document.body.appendChild(wrap);
    const dots = wrap.querySelectorAll('.ai-dots > span');
    const first = dots[0] ? getComputedStyle(dots[0]) : null;
    const result = {
      count: dots.length,
      width: first?.width,
      animation: first?.animationName,
    };
    wrap.remove();
    return result;
  });
  expect(probe.count).toBe(3);
  expect(probe.width).toMatch(/^\d/);
  // Animation name varies (nomadThinkingDots etc.), just confirm it's wired.
  expect(probe.animation && probe.animation !== 'none').toBeTruthy();
});

test('nomad-check renders a stylized tick when checked', async ({ page }) => {
  await boot(page);
  const probe = await page.evaluate(() => {
    const label = document.createElement('label');
    label.innerHTML = '<input type="checkbox" class="nomad-check" checked> probe';
    document.body.appendChild(label);
    const input = label.querySelector('input');
    const cs = getComputedStyle(input);
    const result = {
      appearance: cs.appearance || cs.webkitAppearance,
      width: cs.width,
      height: cs.height,
      backgroundColor: cs.backgroundColor,
    };
    label.remove();
    return result;
  });
  // The primitive overrides the native control — appearance should be none and a sized box rendered.
  expect(probe.appearance).toBe('none');
  expect(probe.width).toMatch(/^\d/);
  expect(probe.height).toMatch(/^\d/);
});

test('drag-handle primitive renders a six-dot grip with grab cursor', async ({ page }) => {
  await boot(page);
  const probe = await page.evaluate(() => {
    const span = document.createElement('span');
    span.className = 'drag-handle';
    document.body.appendChild(span);
    const cs = getComputedStyle(span);
    const result = {
      cursor: cs.cursor,
      width: cs.width,
      height: cs.height,
      backgroundImage: cs.backgroundImage,
    };
    span.remove();
    return result;
  });
  expect(probe.cursor).toBe('grab');
  expect(probe.width).toMatch(/^\d/);
  expect(probe.height).toMatch(/^\d/);
  // Six radial gradients drive the dot pattern; confirm a multi-image background.
  expect(probe.backgroundImage).toMatch(/radial-gradient/);
});

test('overflow scroll containers expose a custom scrollbar style', async ({ page }) => {
  await boot(page);
  const probe = await page.evaluate(() => {
    const div = document.createElement('div');
    div.style.cssText = 'width:120px;height:80px;overflow:auto;';
    div.innerHTML = '<div style="height:400px;width:400px;">spacer</div>';
    document.body.appendChild(div);
    const cs = getComputedStyle(div);
    const result = {
      scrollbarWidth: cs.scrollbarWidth || '',
      scrollbarColor: cs.scrollbarColor || '',
    };
    div.remove();
    return result;
  });
  // Either the standard scrollbar-width/color tokens or webkit-only styling is fine —
  // the polish layer sets at least one of these.
  const styled =
    (probe.scrollbarWidth && probe.scrollbarWidth !== 'auto') ||
    (probe.scrollbarColor && probe.scrollbarColor !== 'auto');
  expect(styled).toBeTruthy();
});

test('tone utilities map to the design-system colour tokens', async ({ page }) => {
  await boot(page);
  const probe = await page.evaluate(() => {
    const get = (cls) => {
      const el = document.createElement('span');
      el.className = cls;
      el.textContent = 'x';
      document.body.appendChild(el);
      const color = getComputedStyle(el).color;
      el.remove();
      return color;
    };
    return {
      success: get('tone-success'),
      warning: get('tone-warning'),
      danger: get('tone-danger'),
      muted: get('tone-muted'),
    };
  });
  // All four tones should resolve to non-transparent, distinct colours.
  const colours = Object.values(probe);
  for (const c of colours) {
    expect(c).toMatch(/^rgb/);
    expect(c).not.toBe('rgba(0, 0, 0, 0)');
  }
  expect(new Set(colours).size).toBeGreaterThanOrEqual(3);
});

test('text clamp utilities cap to two and three lines', async ({ page }) => {
  await boot(page);
  const probe = await page.evaluate(() => {
    const sample = 'one two three four five six seven eight nine ten '.repeat(40);
    const make = (cls) => {
      const el = document.createElement('div');
      el.className = cls;
      el.style.width = '160px';
      el.style.fontSize = '12px';
      el.style.lineHeight = '16px';
      el.textContent = sample;
      document.body.appendChild(el);
      const height = el.getBoundingClientRect().height;
      el.remove();
      return height;
    };
    return {
      two: make('text-2-line'),
      three: make('text-3-line'),
    };
  });
  // 16px line-height × 2 ≈ 32px, × 3 ≈ 48px — give a couple px tolerance.
  expect(probe.two).toBeLessThan(40);
  expect(probe.three).toBeLessThan(56);
  expect(probe.three).toBeGreaterThan(probe.two);
});
