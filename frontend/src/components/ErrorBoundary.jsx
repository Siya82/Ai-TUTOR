/*
 * NEW 19 Nov 2026 (code review 19 Nov #14). If a screen crashes while
 * rendering, show a calm message with a way out instead of a blank page.
 * (Class component: React only catches render errors with one.)
 */
import { Component } from "react";
import { reportClientError } from "../api";

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error("THUTOra screen error", error, info?.componentStack);
    reportClientError(error, info?.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="login-screen">
        <div className="login-screen__card">
          <h1 className="login-screen__title">Something went wrong</h1>
          <p className="login-screen__subtitle">
            This screen hit a problem. Your work is saved — reloading usually fixes it.
          </p>
          <button type="button" onClick={() => window.location.reload()}>
            Reload THUTOra
          </button>
          <button
            type="button"
            className="privacy-link"
            onClick={() => {
              try {
                sessionStorage.clear();
              } catch {
                /* ignore */
              }
              window.location.reload();
            }}
          >
            Log out and start again
          </button>
        </div>
      </div>
    );
  }
}
