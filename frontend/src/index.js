import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';
import { BrowserRouter } from 'react-router-dom';
import reportWebVitals from './reportWebVitals';

const root = ReactDOM.createRoot(document.getElementById('root'));

root.render(
  <React.StrictMode>
    <BrowserRouter future={{ 
      v7_startTransition: true, 
      v7_relativeSplatPath: true 
    }}>
      <App />
    </BrowserRouter>
  </React.StrictMode>
);

// ✅ Measure app performance & log results
reportWebVitals(console.log);
