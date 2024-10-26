// static/js/main.js

// Utility functions to handle API calls and token management

const API_BASE = '/api';

// Function to get token from session storage
function getToken() {
    return sessionStorage.getItem('token');
}

// Function to set token in session storage
function setToken(token) {
    sessionStorage.setItem('token', token);
}

// Function to set username in session storage
function setUsername(username) {
    sessionStorage.setItem('username', username);
}

// Function to get username
function getUsername() {
    return sessionStorage.getItem('username');
}

// Function to clear session
function clearSession() {
    sessionStorage.removeItem('token');
    sessionStorage.removeItem('username');
}

// Show login form
function showLogin() {
    window.location.href = '/login';
}

// Show register form
function showRegister() {
    window.location.href = '/register';
}

// Logout function
function logout() {
    clearSession();
    window.location.href = '/';
}

// Edit notebook
async function editNotebook(id) {
    window.location.href = 'https://rr.alkemata.com/edit/'+id;
}


// Create a new notebook
async function createNotebook() {
    const token = getToken();
    if (!token) {
        alert('You must be logged in to create a notebook.');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/notebooks`, {
            method: 'POST',
            credentials: 'include', // Include cookies in the request
        });

        if (response.status === 201) {
            const data = await response.json();
            const notebookId = data.notebook_id;
            const slug = getUsername();
            window.location.href = `/edit/${notebookId}`;
        } else {
            const error = await response.json();
            alert(`Error: ${error.message}`);
        }
    } catch (err) {
        console.error(err);
        alert('An error occurred while creating the notebook.');
    }
}

// Toggle JupyterLite iframe
function toggleEdit(notebookId) {
    const iframe = document.getElementById('jupyterlite-iframe');
    if (iframe.style.display === 'none') {
        iframe.style.display = 'block';
        iframe.src = `/edit/${notebookId}`;
    } else {
        iframe.style.display = 'none';
    }
}

// Event listeners for login and register forms
document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const username = document.getElementById('login-username').value;
            const password = document.getElementById('login-password').value;

            try {
                const response = await fetch(`${API_BASE}/login`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ username, password }),
                    credentials: 'include',
                });

                const data = await response.json();
                if (response.status === 200) {
                    setToken(data.token);
                    setUsername(username);
                    window.location.href = '/';
                } else {
                    document.getElementById('login-message').innerText = data.message;
                }
            } catch (err) {
                console.error(err);
                document.getElementById('login-message').innerText = 'An error occurred.';
            }
        });
    }

    const registerForm = document.getElementById('register-form');
    if (registerForm) {
        registerForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const username = document.getElementById('register-username').value;
            const password = document.getElementById('register-password').value;

            try {
                const response = await fetch(`${API_BASE}/register`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ username, password }),
                    credentials: 'include', 
                });

                const data = await response.json();
                if (response.status === 201) {
                    // Automatically create a notebook after registration
                    const loginResponse = await fetch(`${API_BASE}/login`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ username, password }),
                    });

                    const loginData = await loginResponse.json();
                    if (loginResponse.status === 200) {
                        setToken(loginData.token);
                        setUsername(username);

                        // Create notebook
                        const notebookResponse = await fetch(`${API_BASE}/notebooks`, {
                            method: 'POST',
                            credentials: 'include', // Include cookies in the request
                        });

                        if (notebookResponse.status === 201) {
                            window.location.href = `/slug/${username}`;
                        } else {
                            alert('Registered but failed to create notebook.');
                        }
                    } else {
                        alert('Registered but failed to login.');
                    }
                } else {
                    document.getElementById('register-message').innerText = data.message;
                }
            } catch (err) {
                console.error(err);
                document.getElementById('register-message').innerText = 'An error occurred.';
            }
        });
    }
});
