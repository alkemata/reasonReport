// static/js/main.js

// Utility functions to handle API calls and token management

const API_BASE = '/api';


// Show login form
function showLogin() {
    window.location.href = '/login';
}

// Show register form
function showRegister() {
    window.location.href = '/register';
}



// Event listeners for login and register forms
document.addEventListener('DOMContentLoaded', () => {

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
