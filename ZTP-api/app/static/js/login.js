// login functionality
// Encrypt the credentials
document
  .getElementById("loginForm")
  .addEventListener("submit", function (event) {
    event.preventDefault();
    console.log("Login form submitted");

    const username = document.getElementById("username").value;
    const password = document.getElementById("password").value;
    localStorage.setItem("loggedInAs", username);
    // Encrypt the credentials
    const encryptedUsername = btoa(username);
    const encryptedPassword = btoa(password);
    const encryptedAuthkey = btoa(username + ":" + password);

    // Store encrypted credentials in local storage
    localStorage.setItem("username", encryptedUsername);
    localStorage.setItem("password", encryptedPassword);
    localStorage.setItem("authkey", encryptedAuthkey);

    console.log("Credentials stored successfully!");
    const existingMessage = document.getElementById("loginMessage");
    if (existingMessage) {
      existingMessage.innerHTML = "";
    } else {
      const loginMessage = document.createElement("div");
      loginMessage.id = "loginMessage";
    }
    fetch("/admin/auth/login_for_ui", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        username: encryptedUsername,
        password: encryptedPassword,
      }),
    })
      .then((response) => {
        console.log(response.status);
        if (response.status === 200) {
          localStorage.setItem("loggedIn", "true");
          loginMessage.innerText = "Login successful.";
          loginMessage.style.color = "green";
          document.getElementById("loginForm").appendChild(loginMessage);
          window.location.href = "/static/index.html";
        }
        if (response.status !== 200) {
          loginMessage.innerText =
            "Login failed. Please check your credentials.";
          loginMessage.style.color = "red";
          document.getElementById("loginForm").appendChild(loginMessage);
        }
      })
      .then((data) => {
        console.log(data);
      })
      .catch((error) => {
        console.error("Error:", error);
        alert("An error occurred during login.");
      });
  });
