# Royal Land Property Management System
## Frontend Architecture Documentation

### Tech Stack Overview

| Layer | Technology | Purpose |
|-------|------------|---------|
| Templating | Django Templates | Server-side HTML rendering |
| Dynamic Interactions | HTMX 1.9+ | AJAX without JavaScript |
| Styling | Tailwind CSS 3.x | Utility-first CSS framework |
| Icons | Heroicons / Lucide | SVG icon system |
| Backend | Django 5.x / Python 3.12 | Application server |
| Database | PostgreSQL 16 | Data persistence |
| Deployment | Hetzner VPS / Ubuntu 22.04 | Production server |

---

## Design System

### Color Palette

```css
/* Primary Colors */
--color-sidebar: #1C0F3F;        /* Deep royal plum */
--color-accent: #C4923A;          /* Royal gold */
--color-accent-light: #E8C07A;    /* Light gold for text */
--color-accent-bg: rgba(196, 146, 58, 0.12); /* Gold tint */

/* Backgrounds */
--color-page-bg: #FAF7F2;         /* Warm cream */
--color-card-bg: #FFFFFF;         /* White */
--color-card-border: #E8E3DB;     /* Warm gray border */

/* Text Colors */
--color-heading: #1A1A2E;         /* Dark navy */
--color-body: #374151;            /* Gray 700 */
--color-muted: #9CA3AF;           /* Gray 400 */
--color-sidebar-muted: rgba(255, 255, 255, 0.5);

/* Status Colors */
--status-available-bg: #D1FAE5;   --status-available-text: #065F46;
--status-booked-bg: #EDE9FE;      --status-booked-text: #4C1D95;
--status-sold-bg: #F3F0EB;        --status-sold-text: #4B5563;
--status-overdue-bg: #FEE2E2;     --status-overdue-text: #991B1B;
--status-pending-bg: #FEF3C7;     --status-pending-text: #92400E;
--status-paid-bg: #D1FAE5;        --status-paid-text: #065F46;
```

### Typography

| Element | Font | Size | Weight |
|---------|------|------|--------|
| Page Title | Inter/system-ui | 24px | 500 |
| Card Title | Inter/system-ui | 16px | 500 |
| Body Text | Inter/system-ui | 14px | 400 |
| Table Header | Inter/system-ui | 11px | 500 (uppercase) |
| Stat Number | Inter/system-ui | 24px | 500 |
| Badge/Pill | Inter/system-ui | 11px | 500 |
| Sidebar Nav | Inter/system-ui | 14px | 400 |
| Section Label | Inter/system-ui | 10px | 500 (uppercase) |

### Component Specifications

#### Cards
- Background: `#FFFFFF`
- Border: `0.5px solid #E8E3DB`
- Border Radius: `10px`
- Padding: `16px`
- Shadow: None (flat design)

#### Buttons
- Primary: `bg-[#C4923A] text-white hover:bg-[#B3832E]`
- Secondary: `bg-white border border-[#E8E3DB] text-[#374151] hover:bg-[#FAF7F2]`
- Border Radius: `6px`
- Padding: `8px 16px`

#### Status Pills
- Border Radius: `20px`
- Font Size: `11px`
- Padding: `4px 12px`

#### Form Inputs
- Border: `1px solid #E8E3DB`
- Focus Border: `#C4923A`
- Border Radius: `6px`
- Padding: `10px 12px`

---

## Layout Architecture

### Page Structure

```
┌─────────────────────────────────────────────────────────────┐
│                        Browser Viewport                       │
├──────────────┬──────────────────────────────────────────────┤
│              │                                               │
│   SIDEBAR    │              MAIN CONTENT AREA                │
│   (Fixed)    │              (Scrollable)                     │
│   220px      │              calc(100% - 220px)               │
│              │                                               │
│  ┌────────┐  │   ┌─────────────────────────────────────┐    │
│  │  Logo  │  │   │          Page Header                │    │
│  └────────┘  │   │   Title + Date + Action Buttons     │    │
│              │   └─────────────────────────────────────┘    │
│  MAIN        │                                               │
│  ─ Dashboard │   ┌─────────────────────────────────────┐    │
│  ─ Projects  │   │          Content Area               │    │
│  ─ Plots     │   │   Cards, Tables, Forms, etc.        │    │
│  ─ Customers │   │                                     │    │
│              │   │                                     │    │
│  FINANCE     │   │                                     │    │
│  ─ Bookings  │   │                                     │    │
│  ─ Install.. │   │                                     │    │
│  ─ Expenses  │   │                                     │    │
│              │   │                                     │    │
│  REPORTS     │   │                                     │    │
│  ─ Challans  │   │                                     │    │
│  ─ Reports   │   └─────────────────────────────────────┘    │
│              │                                               │
│  ┌────────┐  │                                               │
│  │  User  │  │                                               │
│  │ Panel  │  │                                               │
│  └────────┘  │                                               │
└──────────────┴──────────────────────────────────────────────┘
```

---

## HTMX Integration Patterns

### Core Principles

1. **Partial Page Updates**: Use `hx-target` to update specific DOM sections
2. **Boosted Navigation**: Use `hx-boost="true"` for seamless page transitions
3. **Lazy Loading**: Use `hx-trigger="revealed"` for deferred content
4. **Real-time Updates**: Use `hx-trigger="every 30s"` for live data

### Common HTMX Patterns

#### 1. Modal Forms (Create/Edit)
```html
<button hx-get="/bookings/create/" 
        hx-target="#modal-container"
        hx-swap="innerHTML">
  + New Booking
</button>

<div id="modal-container"></div>
```

#### 2. Inline Editing
```html
<span hx-get="/plots/{{ plot.id }}/edit-status/" 
      hx-trigger="click"
      hx-swap="outerHTML">
  {{ plot.status }}
</span>
```

#### 3. Table Row Updates
```html
<tr id="installment-{{ id }}" 
    hx-get="/installments/{{ id }}/"
    hx-trigger="payment-recorded from:body"
    hx-swap="outerHTML">
```

#### 4. Search with Debounce
```html
<input type="search" 
       name="q"
       hx-get="/plots/search/"
       hx-target="#plot-results"
       hx-trigger="keyup changed delay:300ms"
       hx-indicator="#search-spinner">
```

#### 5. Infinite Scroll / Pagination
```html
<div hx-get="/installments/?page={{ next_page }}"
     hx-trigger="revealed"
     hx-swap="afterend"
     hx-indicator="#loading">
  Loading more...
</div>
```

#### 6. Form Submission with Validation
```html
<form hx-post="/bookings/create/"
      hx-target="#form-container"
      hx-swap="outerHTML"
      hx-indicator="#submit-spinner">
```

### HTMX Response Patterns

Django views should return:
- **Partial HTML** for `HX-Request` headers
- **Full page** for normal requests
- **HX-Trigger** headers for cross-component updates

```python
# views.py pattern
def record_payment(request, id):
    # ... process payment
    if request.headers.get('HX-Request'):
        response = render(request, 'partials/installment_row.html', {'installment': obj})
        response['HX-Trigger'] = 'payment-recorded'
        return response
    return redirect('booking-detail', id=obj.booking_id)
```

---

## Page Specifications

### 1. Dashboard

**URL**: `/dashboard/`

**Components**:
- Page header with title, date, and "+ New Booking" CTA
- 4 stat cards in responsive grid (4 cols desktop, 2 cols tablet, 1 col mobile)
- Two-column layout below: Overdue Installments table (60%) + Pending Expenses (40%)

**HTMX Features**:
- Auto-refresh stats every 60 seconds
- Quick actions (Record Payment, Download Challan) in table rows
- Expense approval triggers row removal with animation

### 2. Booking Detail

**URL**: `/bookings/<id>/`

**Components**:
- Three info cards in row: Customer, Plot, Financial Summary
- Progress bar showing payment completion
- Installment schedule table with full CRUD actions

**HTMX Features**:
- Record payment modal updates row in-place
- Download challan generates PDF via HTMX
- Status changes reflect immediately

### 3. Plots List

**URL**: `/plots/`

**Components**:
- Filter bar (project, status, category, search)
- Grid or table view toggle
- Pagination with HTMX

**HTMX Features**:
- Filter changes trigger partial table reload
- Status update dropdown with inline edit
- Bulk selection for batch operations

### 4. Customers List

**URL**: `/customers/`

**Components**:
- Search bar with live results
- Customer cards or table view
- Quick view sidebar/modal

### 5. Booking Form

**URL**: `/bookings/create/` or `/bookings/<id>/edit/`

**Components**:
- Multi-step wizard or single form
- Plot selector with availability check
- Customer lookup/create
- Payment plan configuration
- Preview before submission

---

## Directory Structure (Django Templates)

```
templates/
├── base.html                    # Master layout with sidebar
├── partials/
│   ├── _sidebar.html            # Sidebar navigation
│   ├── _page_header.html        # Page title + actions
│   ├── _stat_card.html          # Reusable stat card
│   ├── _status_pill.html        # Status badge component
│   ├── _modal.html              # Modal container
│   ├── _table_empty.html        # Empty state for tables
│   ├── _pagination.html         # HTMX pagination
│   └── _toast.html              # Notification toast
├── components/
│   ├── _button.html             # Button variants
│   ├── _input.html              # Form input
│   ├── _select.html             # Select dropdown
│   ├── _card.html               # Card wrapper
│   └── _avatar.html             # User avatar
├── dashboard/
│   ├── index.html               # Dashboard page
│   ├── _stats_row.html          # Stats cards partial
│   ├── _overdue_table.html      # Overdue installments
│   └── _pending_expenses.html   # Pending expenses list
├── bookings/
│   ├── list.html                # Bookings list
│   ├── detail.html              # Booking detail page
│   ├── _form.html               # Create/edit form partial
│   ├── _installment_row.html    # Single installment row
│   └── _customer_card.html      # Customer info card
├── plots/
│   ├── list.html                # Plots list
│   ├── _filter_bar.html         # Filters partial
│   ├── _plot_card.html          # Plot card (grid view)
│   └── _plot_row.html           # Plot row (table view)
├── customers/
│   ├── list.html                # Customers list
│   └── detail.html              # Customer detail
├── installments/
│   ├── list.html                # All installments
│   └── _payment_modal.html      # Record payment modal
├── expenses/
│   ├── list.html                # Expenses list
│   └── _expense_row.html        # Expense row partial
└── reports/
    ├── challans.html            # PDF challans page
    └── reports.html             # Reports dashboard
```

---

## Responsive Breakpoints

| Breakpoint | Width | Sidebar | Layout |
|------------|-------|---------|--------|
| Mobile | < 768px | Hidden (hamburger) | Single column |
| Tablet | 768px - 1024px | Collapsed icons | 2 columns |
| Desktop | > 1024px | Full 220px | Multi-column |

### Mobile Navigation Pattern

```html
<!-- Mobile: Hamburger triggers sidebar overlay -->
<button class="md:hidden" 
        hx-get="/partials/sidebar/"
        hx-target="#mobile-sidebar"
        hx-swap="innerHTML">
  <svg><!-- hamburger icon --></svg>
</button>

<div id="mobile-sidebar" class="fixed inset-0 z-50 hidden">
  <!-- Sidebar overlay -->
</div>
```

---

## Accessibility Guidelines

1. **Semantic HTML**: Use `<nav>`, `<main>`, `<section>`, `<article>` appropriately
2. **ARIA Labels**: Add `aria-label` to icon-only buttons
3. **Focus Management**: Trap focus in modals, restore on close
4. **Color Contrast**: All text meets WCAG AA standards
5. **Keyboard Navigation**: All interactive elements are focusable
6. **Screen Reader**: Use `sr-only` class for descriptive hidden text
7. **Loading States**: Announce loading via `aria-live="polite"`

---

## Performance Considerations

1. **HTMX Partial Loading**: Return minimal HTML fragments
2. **CSS**: Use Tailwind's purge to minimize CSS bundle
3. **Icons**: Inline critical icons, lazy-load others
4. **Images**: Use WebP format, implement lazy loading
5. **Caching**: Leverage Django's template fragment caching
6. **Compression**: Enable gzip/brotli on Hetzner VPS

---

## Security Best Practices

1. **CSRF Tokens**: Always include `{% csrf_token %}` in forms
2. **HTMX Security**: Use `hx-headers` for CSRF in AJAX requests
3. **Content Security Policy**: Configure appropriate CSP headers
4. **Input Sanitization**: Server-side validation for all inputs
5. **XSS Prevention**: Use Django's auto-escaping in templates

```html
<!-- HTMX CSRF Configuration -->
<body hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>
```

---

## Integration Checklist

- [ ] Install Tailwind CSS via npm or CDN
- [ ] Include HTMX via CDN or static files
- [ ] Configure `tailwind.config.js` with custom colors
- [ ] Set up Django template directories
- [ ] Create base layout with sidebar
- [ ] Implement CSRF token handling for HTMX
- [ ] Test responsive breakpoints
- [ ] Verify accessibility compliance
- [ ] Optimize for production deployment
