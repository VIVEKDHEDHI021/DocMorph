# UI Component Inventory
## DocMorph Modern Frontend Architecture

### 1. Reusable Design Components

| Component | File Path | Purpose |
| :--- | :--- | :--- |
| `FloatingGlassNavigation` | `frontend/src/components/FloatingGlassNavigation.tsx` | Main floating capsule navigation housing Home, Iridescent Add PDF button, and Profile. |
| `IridescentAddButton` | `frontend/src/components/IridescentAddButton.tsx` | Elevated, iridescent floating action button with chromatic glow and tap animation. |
| `CompactHeader` | `frontend/src/components/CompactHeader.tsx` | Minimal top app bar with DocMorph logo, offline status tag, and profile access. |
| `DocumentCard` | `frontend/src/components/DocumentCard.tsx` | Clean document row card with icon, filename, page count, status pill, and action buttons. |
| `ProfileSettingsModal` | `frontend/src/components/ProfileSettingsModal.tsx` | Tabbed dialog for Student Profile management and offline backend configuration. |
| `ProfileSetupModal` | `frontend/src/components/ProfileSetupModal.tsx` | Compact initial setup dialog for student name and enrollment number. |
| `PdfViewer` | `frontend/src/components/PdfViewer.tsx` | Interactive PDF.js canvas with zoom, page navigation, and Smart Select integration. |
| `SmartSelectionOverlay` | `frontend/src/components/SmartSelectionOverlay.tsx` | Galaxy AI / Circle-to-Search selection overlay supporting rectangular and text selection. |

---

### 2. Screen & Page Architecture

| Screen / Page | Route | Description |
| :--- | :--- | :--- |
| `HomePage` | `/`, `/home`, `/dashboard` | Consolidated main workspace merging Home and Dashboard into a clean document library. |
| `WorkspacePage` | `/workspace/:documentId` | 4-step workflow: Preview, Review, Personalize, and Export with live PDF verification. |
| `LandingPage` | (Legacy alias) | Redirects/serves `HomePage` cleanly without duplicate routing. |
| `DashboardPage` | (Legacy alias) | Re-exports `HomePage` ensuring complete backwards compatibility. |
