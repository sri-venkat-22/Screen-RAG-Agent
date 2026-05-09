# Frontend Engineer Knowledge Base

## React Rendering And State
Frontend engineers should understand how UI state flows through components and how rendering work becomes visible to users. Strong React architecture keeps server state, local interaction state, form state, and derived display state separate. Unnecessary global state makes debugging harder, while overly local state can create duplication and synchronization bugs. Good candidates explain tradeoffs around controlled components, server cache libraries, optimistic updates, hydration, and error boundaries.

## Browser Performance
Performance work starts with measurement. Core Web Vitals, JavaScript execution time, bundle size, network waterfalls, hydration cost, and long tasks help explain why an interface feels slow. Improvements include code splitting, image optimization, prefetching, reducing main-thread work, avoiding unnecessary re-renders, and keeping critical interactions responsive. A strong answer connects optimizations to user-visible outcomes rather than naming tools alone.

## Accessibility And Interaction Quality
Accessible interfaces use semantic HTML, keyboard navigation, focus management, color contrast, labels, and predictable interaction patterns. Accessibility is not a final polish pass; it shapes component APIs and design system primitives. Complex widgets need ARIA only when native semantics are insufficient. Good candidates know how to test with keyboard-only navigation, screen readers, automated checks, and manual review.

## Component Architecture And Design Systems
Reusable components should expose clear behavior, stable styling hooks, and safe defaults. Design systems scale when they document states such as loading, empty, disabled, error, selected, and overflow. Breaking changes require migration paths, codemods or compatibility wrappers, and communication with product teams. Strong engineers avoid abstracting too early but also recognize when duplication is hiding shared product behavior.

## Testing And Reliability
Frontend tests should focus on behavior that users depend on. Unit tests are useful for pure logic and small components, integration tests cover flows, and browser tests catch layout and interaction issues. Resilient clients handle partial failures, slow networks, stale data, and offline transitions where relevant. Good answers include observability through client logs, performance monitoring, and error reporting.

