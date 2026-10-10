// ==============================================================================
// POINT D'ENTRÉE REACT (frontend/src/main.jsx)
// Montage de l'application React dans le DOM
// ==============================================================================

// Importation de la bibliothèque React principale
import React from 'react';

// Importation du moteur de rendu DOM pour React 18
import ReactDOM from 'react-dom/client';

// Importation du composant racine de l'application
import App from './App.jsx';

// Importation de la feuille de style globale
import './index.css';

// Montage de l'application dans l'élément racine #root avec le StrictMode
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
