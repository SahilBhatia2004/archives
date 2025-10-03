import React, { useState, useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import axios from "axios";
import "./App.css";
import { Button } from "./components/ui/button";
import { Input } from "./components/ui/input";
import { Card } from "./components/ui/card";
import { Toaster } from "./components/ui/toaster";
import { useToast } from "./hooks/use-toast";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Login Page
const LoginPage = ({ onLogin }) => {
  const [isSignup, setIsSignup] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState("clerk");
  const [loading, setLoading] = useState(false);
  const { toast } = useToast();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const endpoint = isSignup ? "/auth/signup" : "/auth/login";
      const payload = isSignup
        ? { email, password, role, full_name: fullName }
        : { email, password };

      const response = await axios.post(`${API}${endpoint}`, payload);
      
      const userData = {
        token: response.data.access_token,
        userId: response.data.user_id,
        email: response.data.email,
        role: response.data.role,
      };

      localStorage.setItem("authToken", userData.token);
      localStorage.setItem("userData", JSON.stringify(userData));
      
      toast({
        title: "Success",
        description: response.data.message,
      });

      onLogin(userData);
    } catch (error) {
      toast({
        title: "Error",
        description: error.response?.data?.detail || "Authentication failed",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-card">
        <div className="logo-section">
          <div className="army-emblem">
            <svg viewBox="0 0 100 100" className="emblem-svg">
              <circle cx="50" cy="50" r="45" fill="none" stroke="#C5A572" strokeWidth="3"/>
              <polygon points="50,20 60,45 85,45 65,60 72,85 50,70 28,85 35,60 15,45 40,45" fill="#C5A572"/>
            </svg>
          </div>
          <h1 className="army-title">Indian Army</h1>
          <h2 className="system-title">Document Management System</h2>
        </div>

        <div className="form-section">
          <h3 data-testid="auth-form-title">{isSignup ? "Create Account" : "Sign In"}</h3>
          
          <form onSubmit={handleSubmit}>
            {isSignup && (
              <div className="form-group">
                <Input
                  data-testid="signup-fullname-input"
                  type="text"
                  placeholder="Full Name"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  required
                />
              </div>
            )}

            <div className="form-group">
              <Input
                data-testid="auth-email-input"
                type="email"
                placeholder="Email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <Input
                data-testid="auth-password-input"
                type="password"
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>

            {isSignup && (
              <div className="form-group role-selection">
                <label>Select Your Role:</label>
                <div className="role-buttons">
                  <button
                    type="button"
                    data-testid="role-clerk-button"
                    className={`role-btn ${role === "clerk" ? "active" : ""}`}
                    onClick={() => setRole("clerk")}
                  >
                    <span>📄</span>
                    <span>Clerk</span>
                    <small>Upload Documents</small>
                  </button>
                  <button
                    type="button"
                    data-testid="role-officer-button"
                    className={`role-btn ${role === "officer" ? "active" : ""}`}
                    onClick={() => setRole("officer")}
                  >
                    <span>🔍</span>
                    <span>Officer</span>
                    <small>Search Documents</small>
                  </button>
                </div>
              </div>
            )}

            <Button 
              data-testid="auth-submit-button"
              type="submit" 
              className="submit-btn" 
              disabled={loading}
            >
              {loading ? "Please wait..." : isSignup ? "Sign Up" : "Sign In"}
            </Button>
          </form>

          <div className="toggle-auth">
            <button 
              data-testid="toggle-auth-mode-button"
              onClick={() => setIsSignup(!isSignup)}
            >
              {isSignup
                ? "Already have an account? Sign In"
                : "Don't have an account? Sign Up"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

// Clerk Dashboard
const ClerkDashboard = ({ userData, onLogout }) => {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [documents, setDocuments] = useState([]);
  const { toast } = useToast();

  useEffect(() => {
    loadDocuments();
  }, []);

  const loadDocuments = async () => {
    try {
      const response = await axios.get(`${API}/documents`, {
        headers: { Authorization: `Bearer ${userData.token}` },
      });
      setDocuments(response.data.documents || []);
    } catch (error) {
      console.error("Failed to load documents:", error);
    }
  };

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
  };

  const handleUpload = async () => {
    if (!file) {
      toast({
        title: "No File Selected",
        description: "Please select a file to upload",
        variant: "destructive",
      });
      return;
    }

    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await axios.post(`${API}/documents/upload`, formData, {
        headers: {
          Authorization: `Bearer ${userData.token}`,
          "Content-Type": "multipart/form-data",
        },
      });

      toast({
        title: "Success",
        description: response.data.message,
      });

      setFile(null);
      document.getElementById("file-input").value = "";
      loadDocuments();
    } catch (error) {
      toast({
        title: "Upload Failed",
        description: error.response?.data?.detail || "Failed to upload document",
        variant: "destructive",
      });
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="dashboard-container">
      <nav className="dashboard-nav">
        <div className="nav-brand">
          <svg viewBox="0 0 100 100" className="nav-emblem">
            <circle cx="50" cy="50" r="45" fill="none" stroke="#C5A572" strokeWidth="3"/>
            <polygon points="50,20 60,45 85,45 65,60 72,85 50,70 28,85 35,60 15,45 40,45" fill="#C5A572"/>
          </svg>
          <span>Army Document System</span>
        </div>
        <div className="nav-user">
          <span className="user-role">Clerk</span>
          <span className="user-email">{userData.email}</span>
          <Button 
            data-testid="logout-button"
            onClick={onLogout} 
            variant="outline" 
            className="logout-btn"
          >
            Logout
          </Button>
        </div>
      </nav>

      <div className="dashboard-content">
        <h1 data-testid="clerk-dashboard-title">Document Upload Center</h1>
        
        <Card className="upload-card">
          <h2>Upload New Document</h2>
          <p className="upload-desc">
            Upload PDF, Word, images, or text files. Text will be automatically extracted for search.
          </p>

          <div className="upload-section">
            <Input
              id="file-input"
              data-testid="file-input"
              type="file"
              onChange={handleFileChange}
              accept=".pdf,.doc,.docx,.txt,.jpg,.jpeg,.png,.gif"
              className="file-input"
            />
            
            {file && (
              <div className="file-preview" data-testid="file-preview">
                <span className="file-icon">📄</span>
                <div className="file-info">
                  <p className="file-name">{file.name}</p>
                  <p className="file-size">
                    {(file.size / 1024).toFixed(2)} KB
                  </p>
                </div>
              </div>
            )}

            <Button
              data-testid="upload-button"
              onClick={handleUpload}
              disabled={uploading || !file}
              className="upload-btn"
            >
              {uploading ? "Uploading..." : "Upload Document"}
            </Button>
          </div>
        </Card>

        <Card className="documents-list">
          <h2>Uploaded Documents ({documents.length})</h2>
          <div className="documents-grid">
            {documents.map((doc) => (
              <div key={doc.id} className="document-item" data-testid={`document-item-${doc.id}`}>
                <div className="doc-icon">📄</div>
                <div className="doc-info">
                  <p className="doc-name">{doc.name}</p>
                  <p className="doc-size">{(doc.size / 1024).toFixed(2)} KB</p>
                  <p className="doc-date">
                    {new Date(doc.upload_date).toLocaleDateString()}
                  </p>
                  <div className="doc-keywords">
                    {doc.keywords.slice(0, 3).map((kw, i) => (
                      <span key={i} className="keyword-tag">{kw}</span>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
};

// Officer Dashboard
const OfficerDashboard = ({ userData, onLogout }) => {
  const [searchQuery, setSearchQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState([]);
  const { toast } = useToast();

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      toast({
        title: "Empty Query",
        description: "Please enter a search query",
        variant: "destructive",
      });
      return;
    }

    setSearching(true);

    try {
      const response = await axios.post(
        `${API}/documents/search`,
        {
          query: searchQuery,
          user_id: userData.userId,
        },
        {
          headers: { Authorization: `Bearer ${userData.token}` },
        }
      );

      setResults(response.data);

      if (response.data.length === 0) {
        toast({
          title: "No Results",
          description: "No documents found matching your query",
        });
      }
    } catch (error) {
      toast({
        title: "Search Failed",
        description: error.response?.data?.detail || "Search operation failed",
        variant: "destructive",
      });
    } finally {
      setSearching(false);
    }
  };

  return (
    <div className="dashboard-container">
      <nav className="dashboard-nav">
        <div className="nav-brand">
          <svg viewBox="0 0 100 100" className="nav-emblem">
            <circle cx="50" cy="50" r="45" fill="none" stroke="#C5A572" strokeWidth="3"/>
            <polygon points="50,20 60,45 85,45 65,60 72,85 50,70 28,85 35,60 15,45 40,45" fill="#C5A572"/>
          </svg>
          <span>Army Document System</span>
        </div>
        <div className="nav-user">
          <span className="user-role">Officer</span>
          <span className="user-email">{userData.email}</span>
          <Button 
            data-testid="logout-button"
            onClick={onLogout} 
            variant="outline" 
            className="logout-btn"
          >
            Logout
          </Button>
        </div>
      </nav>

      <div className="dashboard-content">
        <h1 data-testid="officer-dashboard-title">AI-Powered Document Search</h1>

        <Card className="search-card">
          <div className="search-section">
            <Input
              data-testid="search-input"
              type="text"
              placeholder="Search documents by name or keywords (e.g., 'training manual', 'logistics report')..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyPress={(e) => e.key === "Enter" && handleSearch()}
              className="search-input"
            />
            <Button
              data-testid="search-button"
              onClick={handleSearch}
              disabled={searching}
              className="search-btn"
            >
              {searching ? "Searching..." : "Search"}
            </Button>
          </div>
        </Card>

        {results.length > 0 && (
          <Card className="results-card">
            <h2 data-testid="search-results-title">Search Results ({results.length})</h2>
            <div className="results-list">
              {results.map((result) => (
                <div 
                  key={result.document_id} 
                  className="result-item"
                  data-testid={`result-item-${result.document_id}`}
                >
                  <div className="result-header">
                    <div className="result-icon">📄</div>
                    <div className="result-info">
                      <h3 className="result-name">{result.document_name}</h3>
                      <div className="result-meta">
                        <span className="result-score">
                          Relevance: {(result.relevance_score * 100).toFixed(0)}%
                        </span>
                        <span className="result-date">
                          {new Date(result.upload_date).toLocaleDateString()}
                        </span>
                      </div>
                    </div>
                  </div>
                  <div className="result-content">
                    <p>{result.matched_content}</p>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}

        {results.length === 0 && !searching && (
          <Card className="empty-state">
            <svg viewBox="0 0 100 100" className="empty-icon">
              <circle cx="50" cy="50" r="30" fill="none" stroke="#4A5568" strokeWidth="2"/>
              <path d="M 65 65 L 80 80" stroke="#4A5568" strokeWidth="3" strokeLinecap="round"/>
            </svg>
            <h3>Start Searching</h3>
            <p>
              Use the search bar above to find documents by name or keywords.
              Our AI will analyze document contents and find the most relevant matches.
            </p>
          </Card>
        )}
      </div>
    </div>
  );
};

// Main App Component
function App() {
  const [userData, setUserData] = useState(null);

  useEffect(() => {
    // Check for existing auth token
    const token = localStorage.getItem("authToken");
    const storedUserData = localStorage.getItem("userData");

    if (token && storedUserData) {
      setUserData(JSON.parse(storedUserData));
    }
  }, []);

  const handleLogin = (userData) => {
    setUserData(userData);
  };

  const handleLogout = () => {
    localStorage.removeItem("authToken");
    localStorage.removeItem("userData");
    setUserData(null);
  };

  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route
            path="/"
            element={
              userData ? (
                userData.role === "clerk" ? (
                  <ClerkDashboard userData={userData} onLogout={handleLogout} />
                ) : (
                  <OfficerDashboard userData={userData} onLogout={handleLogout} />
                )
              ) : (
                <LoginPage onLogin={handleLogin} />
              )
            }
          />
        </Routes>
      </BrowserRouter>
      <Toaster />
    </div>
  );
}

export default App;