// ==============================================================================
// CONFIGURATION VITE (frontend/vite.config.js)
// Configuration du serveur de développement et du plugin React
// ==============================================================================

// Importation de la fonction de configuration Vite
import { defineConfig } from 'vite';

// Importation du plugin officiel React
import react from '@vitejs/plugin-react';

// Exportation de la configuration
export default defineConfig({
  // Activation du plugin React avec Fast Refresh
  plugins: [react()],
  // Configuration du serveur de développement local
  server: {
    // Port d'écoute du frontend React
    port: 5173,
    // Ouverture automatique du navigateur
    open: true,
    // Proxy transparent vers le backend FastAPI
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
});
