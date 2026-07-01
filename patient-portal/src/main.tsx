import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "@cloudscape-design/global-styles/index.css";
import App from "./App";
import { AuthProvider } from "./auth/AuthContext";
import { FlashbarProvider } from "./context/FlashbarContext";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <FlashbarProvider>
        <AuthProvider>
          <App />
        </AuthProvider>
      </FlashbarProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
