/* login */

// glbal variable to store the username
let username = ""
let authkey = ""

//  list of admin users
list_of_admin_users = ["lab_user_01", "lab_user_02", "lab_user_03", "lab_user_04"]

// enable login by uncommenting the below code login()
login()

function login() {
  if (localStorage.getItem("loggedIn") !== "true") {
    console.log("Not logged in");
    window.location.href = "/static/login.html";
  } else {
    const encryptedUsername = localStorage.getItem("username");
    username = atob(encryptedUsername);
    console.log("username:", username);
    authkey = localStorage.getItem("authkey");
    // console.log(authkey);
    if (username) {
      const usernameblock = document.getElementById("userName");
      usernameblock.innerHTML = `${username}`;
      document.getElementById("loginButton").style.display = "none";
    }
  }
}

function logout() {
  localStorage.setItem("loggedIn", "false");
  localStorage.removeItem("username");
  localStorage.removeItem("decryptedUsername");
  localStorage.removeItem("password");
  localStorage.removeItem("encryptedPassword");
  window.location.href = "/static/login.html";
}


let hostsList = [];
const adminlocheckUri = "/bmo/lom/adminlo/credcheck/";
const adminlopatchUri = "/bmo/lom/adminlo/credpatch/";
const adminloadduser = "/bmo/lom/adminlo/adduser/"
const deletecompanylo = "/bmo/lom/companylo/removeuser/"
const eskmpatchUri = "/bmo/iLO/ESKM/cert/";
const eskmcheckUri = "/bmo/iLO/ESKM/status/";
const baselinehpspp = "/baseline/hp/spp/";

// eskm
const eskmFileInput = document.getElementById("eskmFileInput");
const output1 = document.getElementById("eskmOutput");
if (eskmFileInput && output1) {
  handleFileUpload(eskmFileInput, output1);
}

// adminlo
const adminloFileInput = document.getElementById("adminloFileInput");
const output2 = document.getElementById("adminloOutput");
if (adminloFileInput && output2) {
  handleFileUpload(adminloFileInput, output2);
}


function toggleSubmenuBmo(event) {
  event.preventDefault();
  const submenu = event.target.nextElementSibling;
  if (submenu.style.display === "none" || submenu.style.display === "") {
    submenu.style.display = "block";
  } else {
    submenu.style.display = "none";
  }
}


function showSection(sectionId) {
  if (sectionId === "adminservicesForm") {
    console.log(username)
    if (!list_of_admin_users.includes(username)) {
      alert("You are not authorized to access this service");
      return;
    }
  }

  ["BMBuilds", "Linux", "Windows", "Esxi", "myrequests", "BMOps", "eskm", "adminlo", "networkdataForm", "adminservicesForm", "contactUs"].forEach((id) => {
    document.getElementById(id).style.display = "none";
  });

  ["linuxOutput", "windowsOutput", "esxiOutput", "myrequestsOutput", "eskmOutput", "adminloOutput", "networkdataOutput", "adminservicesOutput"].forEach((id) => {
    document.getElementById(id).innerHTML = "";
  });

  document
    .querySelectorAll("input[type='text'], input[type='file']")
    .forEach((input) => {
      input.value = "";
    });

  const sections = document.querySelectorAll("section");
  sections.forEach((section) => {
    // console.log(section);
    section.style.display = "none";
  });

  document.getElementById(sectionId).style.display = "block";

  if (sectionId === "Linux") {
    document.getElementById('host_linux').value = '';
    document.getElementById('os_linux').selectedIndex = 0;
    document.getElementById('role_linux').selectedIndex = 0;
    document.getElementById('data_raid_linux').selectedIndex = 0;
    document.getElementById('deploy_only_false_linux').checked = true;
    document.getElementById('deploy_only_true_linux').checked = false;
    document.getElementById('overrideKey').selectedIndex = 0;
    document.getElementById('overrideValue').value = '';
    document.getElementById('overrideYesBlock').style.display = "none";
    document.getElementById('jsonOutput_linux').value = '';
    document.getElementById('linuxOutput').innerHTML = '';
    const startLinuxBuildButton = document.getElementById("startLinuxBuild");
    startLinuxBuildButton.innerText = "Start Build";
    startLinuxBuildButton.style.backgroundColor = "";
    startLinuxBuildButton.disabled = false;
  }
  if (sectionId === "Esxi") {
    document.getElementById('host_esxi').value = '';
    document.getElementById('os_esxi').selectedIndex = 0;
    document.getElementById('vlan_esxi').value = '3020';
    document.getElementById('deploy_only_false_esxi').checked = true;
    document.getElementById('deploy_only_true_esxi').checked = false;
    document.getElementById('jsonOutput_esxi').value = '';
    document.getElementById('esxiOutput').innerHTML = '';
    const startESXiBuildButton = document.getElementById("startEsxiBuild");
    startESXiBuildButton.innerText = "Start Build";
    startESXiBuildButton.style.backgroundColor = "";
    startESXiBuildButton.disabled = false;
  }
  if (sectionId === "Windows") {
    document.getElementById('host_windows').value = '';
    document.getElementById('os_windows').selectedIndex = 0;
    document.getElementById('jsonOutput_windows').value = '';
    document.getElementById('windowsOutput').innerHTML = '';
    const startWindowsBuildButton = document.getElementById("startWindowsBuild");
    startWindowsBuildButton.innerText = "Start Build";
    startWindowsBuildButton.style.backgroundColor = "";
    startWindowsBuildButton.disabled = false;
  }
}

function handleFileUpload(fileInput, output) {
  fileInput.addEventListener("change", function () {
    document.getElementById("eskmHostInput").value = "";
    document.getElementById("adminloHostInput").value = "";
    const file = fileInput.files[0]; // Get the selected file
    if (file) {
      // console.log("File name:", file.name);
      output.textContent = `File Name: ${file.name}\n\n`; // Display the file name and clear the output area
      const reader = new FileReader(); // Create a FileReader object
      reader.onload = function (e) {
        output.textContent += e.target.result; // Display the file content
        hostsList = e.target.result
          .split("\n")
          .map((line) => line.trim())
          .filter((line) => line !== "");
        if (hostsList.length === 0) {
          alert("The uploaded file is empty or contains only whitespace.");
          document.getElementById("patcheskmButton").disabled = true;
          document.getElementById("patcheskmButton").style.backgroundColor =
            "gray";
          return;
        }
        if (hostsList.length > 100) {
          alert(
            "File uploaded successfully! but The number of hosts exceeds the limit of 100."
          );
          document.getElementById("patcheskmButton").disabled = true;
          document.getElementById("patcheskmButton").style.backgroundColor =
            "gray";
          return;
        } else {
          alert("File uploaded successfully!");
        }
      };
      reader.readAsText(file); // Read the file as text
    }
  });
}

async function checkEskm() {
  const startTime = Date.now();
  const outputDiv = document.getElementById("eskmOutput");
  const hostInput = document.getElementById("eskmHostInput").value;
  const fileInput = document.getElementById("eskmFileInput");
  const lomuser = document.getElementById("ilouser").value;
  const lompass = document.getElementById("ilopass").value;

  if (hostInput.trim() !== "") {
    hostsList = hostInput
      .split(",")
      .map((host) => host.trim())
      .filter((host) => host !== "");
    eskmFileInput.value = "";
    if (hostsList.length > 100) {
      alert("The number of hosts exceeds the limit of 100.");
      return;
    }
  }
  if (hostInput.trim() === "" && (!fileInput || !fileInput.files.length)) {
    alert(
      "Please enter a server/hostname or upload a file with server names each on a new line."
    );
    return;
  }
  if (fileInput && fileInput.files.length > 0) {
    if (hostsList.length === 0) {
      // console.log(hostsList.length);
      alert("The uploaded file is empty or contains only whitespace.");
      return;
    }
  }
  outputDiv.innerHTML = `<div class="processing">Processing...</div>`;
  data = {};
  // console.log(hostsList);
  const promises = hostsList.map(async (host) => {
    if (lomuser.trim() !== "" && lompass.trim() !== "") {
      // console.log("lomuser and lompass are provided");
      const encryptedUsername = btoa(lomuser);
      const encryptedPassword = btoa(lompass);
      const params = new URLSearchParams({
        username: encryptedUsername,
        password: encryptedPassword,

      });
      url = `${eskmcheckUri}${host}?${params.toString()}`;
      console.log(url);
    } else {
      // console.log("without lomuser and lompass");
      url = `${eskmcheckUri}${host}`;
    }
    const responseData = await _fetchDataFromUrl(url);
    data[host] = responseData;
  });
  await Promise.all(promises);
  const endTime = Date.now();
  const elapsedTime = (endTime - startTime) / 1000;
  const time = `Elapsed time: ${elapsedTime} seconds`;
  data[time] = { STATUS: "", TIME: "" };
  await displayDataAsTable(data, (outputContent = "eskmOutput"));
}

async function patchEskm() {
  const startTime = Date.now();
  const outputDiv = document.getElementById("eskmOutput");
  const hostInput = document.getElementById("eskmHostInput").value;
  const fileInput = document.getElementById("eskmFileInput");
  const lomuser = document.getElementById("ilouser").value;
  const lompass = document.getElementById("ilopass").value;

  if (hostInput.trim() !== "") {
    hostsList = hostInput
      .split(",")
      .map((host) => host.trim())
      .filter((host) => host !== "");
    eskmFileInput.value = "";
    if (hostsList.length > 100) {
      alert("The number of hosts exceeds the limit of 100.");
      return;
    }
  }
  if (hostInput.trim() === "" && (!fileInput || !fileInput.files.length)) {
    alert(
      "Please enter a server/hostname or upload a file with server names each on a new line."
    );
    return;
  }
  if (fileInput && fileInput.files.length > 0) {
    if (hostsList.length === 0) {
      // console.log(hostsList.length);
      alert("The uploaded file is empty or contains only whitespace.");
      return;
    }
  }
  outputDiv.innerHTML = `<div class="processing">Processing...</div>`;
  const data = {};
  // console.log(hostsList);
  const promises = hostsList.map(async (host) => {
    if (lomuser.trim() !== "" && lompass.trim() !== "") {
      // console.log("lomuser and lompass are provided");
      const encryptedUsername = btoa(lomuser);
      const encryptedPassword = btoa(lompass);
      const params = new URLSearchParams({
        username: encryptedUsername,
        password: encryptedPassword,

      });
      url = `${eskmpatchUri}${host}?${params.toString()}`;
    } else {
      // console.log("without lomuser and lompass");
      url = `${eskmpatchUri}${host}`;
    }
    const responseData = await _patchDataToUrl(url);
    data[host] = responseData;
  });
  await Promise.all(promises);
  const endTime = Date.now();
  const elapsedTime = (endTime - startTime) / 1000;
  const time = `Elapsed time: ${elapsedTime} seconds`;
  data[time] = { STATUS: "", TIME: "" };
  await displayDataAsTable(data, "eskmOutput");
}

async function _fetchDataFromUrl(url) {
  try {
    const response = await fetch(url);
    const data = await response.json();
    return data;
  } catch (error) {
    console.error("Error fetching data:", error);
  }
}

//
// Adminlo section
//

function validateAdminLoInputs() {
  const user = document.getElementById('lomuser4adminlo').value.trim();
  const pass = document.getElementById('lompass4adminlo').value.trim();
  if ((user && !pass) || (!user && pass)) {
    alert('[iLO or iDRAC user and password:] section requires both input if one is entered.');
    return false;
  }
  return true;
}


async function checkAdminLo() {
  console.log("fn: checkAdminLo");
  const startTime = Date.now();
  const outputDiv = document.getElementById("adminloOutput");
  const hostInput = document.getElementById("adminloHostInput").value;
  const fileInput = document.getElementById("adminloFileInput");
  if (hostInput.trim() !== "") {
    hostsList = hostInput
      .split(",")
      .map((host) => host.trim())
      .filter((host) => host !== "");
    eskmFileInput.value = "";
    if (hostsList.length > 100) {
      alert("The number of hosts exceeds the limit of 100.");
      return;
    }
  }
  if (hostInput.trim() === "" && (!fileInput || !fileInput.files.length)) {
    alert(
      "Please enter a server/hostname or upload a file with server names each on a new line."
    );
    return;
  }
  outputDiv.innerHTML = `<div class="processing adminlo">Processing...</div>`;
  data = {};
  console.log(hostsList);
  const promises = hostsList.map(async (host) => {
    const url = `${adminlocheckUri}${host}`;
    console.log(url);
    const responseData = await _fetchDataFromUrl(url);
    data[host] = responseData;
  });
  await Promise.all(promises);
  const endTime = Date.now();
  const elapsedTime = (endTime - startTime) / 1000;
  const time = `Elapsed time: ${elapsedTime} seconds`;
  data[time] = { STATUS: "", TIME: "" };
  await displayDataAsTable(data, (outputContent = "adminloOutput"));
}// console.log(hostsList);


async function patch_add_AdminLo(add_account = false) {
  console.log("fn:patchAdminLo");
  const startTime = Date.now();
  const outputDiv = document.getElementById("adminloOutput");
  const hostInput = document.getElementById("adminloHostInput").value;
  const fileInput = document.getElementById("adminloFileInput");
  const lomuser = document.getElementById("lomuser4adminlo").value;
  const lompass = document.getElementById("lompass4adminlo").value;
  if (!validateAdminLoInputs()) {
    return;
  }
  if (hostInput.trim() !== "") {
    hostsList = hostInput
      .split(",")
      .map((host) => host.trim())
      .filter((host) => host !== "");
    eskmFileInput.value = "";
    if (hostsList.length > 100) {
      alert("The number of hosts exceeds the limit of 100.");
      return;
    }
  }
  if (hostInput.trim() === "" && (!fileInput || !fileInput.files.length)) {
    alert(
      "Please enter a server/hostname or upload a file with server names each on a new line."
    );
    return;
  }
  outputDiv.innerHTML = `<div class="processing adminlo">Processing...</div>`;
  data = {};
  console.log(hostsList);
  const promises = hostsList.map(async (host) => {
    if (lomuser.trim() !== "" && lompass.trim() !== "") {
      console.log("lomuser and lompass are provided");
      const encryptedUsername = btoa(lomuser);
      const encryptedPassword = btoa(lompass);
      const params = new URLSearchParams({
        username: encryptedUsername,
        password: encryptedPassword,

      });
      if (add_account) {
        url = `${adminloadduser}${host}?${params.toString()}`;
      }
      else {
        url = `${adminlopatchUri}${host}?${params.toString()}`;
      }
    } else {
      console.log("without lomuser and lompass");
      if (add_account) {
        url = `${adminloadduser}${host}`;
      }
      else {
        url = `${adminlopatchUri}${host}`;
      }
    }
    console.log(url);
    const responseData = await _patchDataToUrl(url);
    data[host] = responseData;
  });
  await Promise.all(promises);
  const endTime = Date.now();
  const elapsedTime = (endTime - startTime) / 1000;
  const time = `Elapsed time: ${elapsedTime} seconds`;
  data[time] = { STATUS: "", TIME: "" };
  await displayDataAsTable(data, (outputContent = "adminloOutput"));
}// console.log(hostsList);



async function deleteAdminLo() {
  console.log("fn:deleteAdminLo");
  const startTime = Date.now();
  const outputDiv = document.getElementById("adminloOutput");
  const hostInput = document.getElementById("adminloHostInput").value;
  const fileInput = document.getElementById("adminloFileInput");
  const lomuser = document.getElementById("lomuser4adminlo").value;
  const lompass = document.getElementById("lompass4adminlo").value;
  if (!validateAdminLoInputs()) {
    return;
  }
  if (hostInput.trim() !== "") {
    hostsList = hostInput
      .split(",")
      .map((host) => host.trim())
      .filter((host) => host !== "");
    eskmFileInput.value = "";
    if (hostsList.length > 100) {
      alert("The number of hosts exceeds the limit of 100.");
      return;
    }
  }
  if (hostInput.trim() === "" && (!fileInput || !fileInput.files.length)) {
    alert(
      "Please enter a server/hostname or upload a file with server names each on a new line."
    );
    return;
  }
  outputDiv.innerHTML = `<div class="processing adminlo">Processing...</div>`;
  data = {};
  console.log(hostsList);
  const promises = hostsList.map(async (host) => {
    if (lomuser.trim() !== "" && lompass.trim() !== "") {
      console.log("lomuser and lompass are provided");
      const encryptedUsername = btoa(lomuser);
      const encryptedPassword = btoa(lompass);
      const params = new URLSearchParams({
        username: encryptedUsername,
        password: encryptedPassword,

      });
      url = `${deletecompanylo}${host}?${params.toString()}`;
    } else {
      console.log("without lomuser and lompass");
      url = `${deletecompanylo}${host}`;
    }
    console.log(url);
    const responseData = await _deleteDataFromUrl(url);
    data[host] = responseData;
  });
  await Promise.all(promises);
  const endTime = Date.now();
  const elapsedTime = (endTime - startTime) / 1000;
  const time = `Elapsed time: ${elapsedTime} seconds`;
  data[time] = { STATUS: "", TIME: "" };
  await displayDataAsTable(data, (outputContent = "adminloOutput"));
}// console.log(hostsList);

async function _deleteDataFromUrl(url) {
  try {
    const response = await fetch(url, { method: "DELETE" });
    const data = await response.json();
    return data;
  } catch (error) {
    console.error("Error deleting data:", error);
  }
}

async function _patchDataToUrl(url) {
  try {
    // console.log(url);
    const response = await fetch(url, { method: "PATCH" });
    const data = await response.json();
    return data;
  } catch (error) {
    console.error("Error patching data:", error);
  }
}

async function _patchWithPayload(url, payload) {
  try {
    // console.log("payload:", payload);
    const response = await fetch(url, {
      method: "PATCH",
      body: JSON.stringify(payload),
      headers: {
        "Content-Type": "application/json",
      },
    });
    const data = await response.json();
    return data;
  } catch (error) {
    console.error("Error patching data:", error);
  }
}

async function displayDataAsTable(data, outputContent) {
  console.log(data);
  const outputDiv = document.getElementById(outputContent);
  outputDiv.innerHTML = `<h3> Results: </h3>`;
  const exportButton = document.createElement("button");
  exportButton.innerText = "Export to Excel";
  exportButton.onclick = exportTableToExcel;
  document.getElementById(outputContent).appendChild(exportButton);
  const table = document.createElement("table");
  table.id = "bmo-data-table";
  table.innerHTML = `
    <thead>
      <tr>
        <th>Host</th>
        <th>Status</th>
        <th>LOM User</th>
        <th>Time</th>
        <th>Detail</th>
      </tr>
    </thead>
    <tbody></tbody>
    `;
  outputDiv.appendChild(table);
  const tableBody = document.querySelector("#bmo-data-table tbody");

  for (const key in data) {
    if (data.hasOwnProperty(key)) {
      const item = data[key];
      const row = document.createElement("tr");
      row.innerHTML = `
        <td>${key}</td>
        <td>${item.status}</td>
        <td>${item.requestor}</td>
        <td>${item.time}</td>
        <td>${item.status_detail}</td>
      `;
      if (item.status === "UNCHANGED" || item.status === "WARNING") {
        row.style.backgroundColor = "lightyellow";
      }
      if (item.status === "FAIL") {
        row.style.backgroundColor = "#e5a085";
      }
      if (item.status === "ERROR") {
        row.style.backgroundColor = "lightcoral";
      }
      if (item.status === "SUCCESS" || item.status === "PASS") {
        row.style.backgroundColor = "lightgreen";
      }
      tableBody.appendChild(row);
    }
  }
}


function exportTableToExcel() {
  const fileInput = document.getElementById("eskmFileInput");
  const filename = fileInput.files[0]
    ? fileInput.files[0].name.replace(/\.[^/.]+$/, "") + "_results.xls"
    : "_results.xls";
  const table = document.getElementById("bmo-data-table");
  if (!table) {
    alert("No data available to export");
    return;
  }
  let tableHTML = table.outerHTML.replace(/ /g, "%20");
  const downloadLink = document.createElement("a");
  document.body.appendChild(downloadLink);
  downloadLink.href = "data:application/vnd.ms-excel," + tableHTML;
  downloadLink.download = filename;
  downloadLink.click();
  document.body.removeChild(downloadLink);
}

/* ADMIN services section */

async function fetch_admin_ep(ep) {
  const url = `/admin/builds/${ep}`;
  const response = await fetch(url);
  // showSection("content");
  const outputDiv = document.getElementById("adminservicesOutput");
  if (response.status === 404) {
    outputDiv.innerHTML = `<p style="color: red;"><b>No Request Found today</b></p>`;
    return;
  }
  const data = await response.json();
  outputDiv.innerHTML = `<p><b>Results: ${url}</b></p>`;
  const table = document.createElement("table");
  table.id = "bmo-data-table";
  table.style.borderRadius = "10px";
  table.innerHTML = `
    <thead>
      <tr>
        <th>Host Name</th>
        <th>Build Type</th>
        <th>Build ID</th>
        <th>Status</th>
        <th>Time</th>
        <th>Requestor</th>
        <th>Log</th>
      </tr>
    </thead>
    <tbody></tbody>
    `;
  outputDiv.appendChild(table);
  const tableBody = document.querySelector("#bmo-data-table tbody");
  for (const key in data) {
    if (data.hasOwnProperty(key)) {
      const item = data[key];
      const row = document.createElement("tr");
      row.innerHTML = `
        <td>${item.host}</td>
        <td>${item.build_type}</td>
        <td>${item.build_id}</td>
        <td>${item.status}</td>
        <td>${item.time}</td>
        <td>${item.requestor.requestor_id}</td>
        <td><a href="${item.metadata.logfile}" target="_blank">View Log</a></td>
      `;
      //<td><button onclick="handleLogClick('${item.metadata.logfile}')">View Log</button></td>
      tableBody.appendChild(row);
    }
  }
}

async function showHealthStatus() {
  url = "/health";
  const response = await fetch(url);
  const healthData = response.status === 404 ? {} : await response.json();
  // showSection("adminservices");
  const outputDiv = document.getElementById("adminservicesOutput");
  outputDiv.innerHTML = `<h2>Health Status: ${healthData["health"]}</h2>`;
  const table = document.createElement("table");
  table.id = "health-status-table";
  table.style.borderRadius = "10px";
  table.innerHTML = `
    <thead>
      <tr>
        <th>Service</th>
        <th>Status</th>
        <th>Version</th>
        <th>Branch</th>
      </tr>
    </thead>
    <tbody></tbody>
  `;
  outputDiv.appendChild(table);
  const tableBody = document.querySelector("#health-status-table tbody");

  for (const service in healthData) {
    if (healthData.hasOwnProperty(service)) {
      const item = healthData[service];
      if (service === "health") {
        continue;
      }
      const row = document.createElement("tr");
      row.innerHTML = `
        <td>${service}</td>
        <td>${item.status}</td>
        <td>${item.detail?.version || "N/A"}</td>
        <td>${item.detail?.branch || "N/A"}</td>
      `;
      if (item.status === "up") {
        row.style.backgroundColor = "lightgreen";
      } else {
        row.style.backgroundColor = "lightcoral";
      }
      tableBody.appendChild(row);
    }
  }

  url = "/monit";
  const resp = await fetch(url);
  const monitData = resp.status === 404 ? {} : await resp.json();
  outputDiv.innerHTML += `<h2>Monit Status:</h2>`;
  const additionalTable = document.createElement("table");
  additionalTable.id = "additional-status-table";
  additionalTable.style.borderRadius = "10px";
  additionalTable.innerHTML = `
    <thead>
      <tr>
        <th>Service</th>
        <th>Status</th>
        <th>Type</th>
      </tr>
    </thead>
    <tbody></tbody>
  `;
  outputDiv.appendChild(additionalTable);
  const additionalTableBody = document.querySelector(
    "#additional-status-table tbody"
  );

  monitData.forEach((item) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${item.Service}</td>
      <td>${item.Status}</td>
      <td>${item.Type}</td>
    `;
    if (item.Status === "OK") {
      row.style.backgroundColor = "lightgreen";
    } else {
      row.style.backgroundColor = "lightcoral";
    }
    additionalTableBody.appendChild(row);
  });
}

/* Data Services Section */

async function get_networkData() {
  const host = document.getElementById("host").value;
  const url = `/networkdata/${host}`;
  fetchData(url);
}

async function get_serverInfo() {
  const host = document.getElementById("host").value;
  const url = `/serverinfo/${host}`;
  fetchData(url);
}

async function get_lorandata() {
  const host = document.getElementById("host").value;
  const url = `/loran/${host}`;
  fetchData(url);
}

async function get_oneview_server() {
  const host = document.getElementById("host").value;
  const url = `/bmo/iLO/oneview/${host}`;
  fetchData(url);
}

async function get_firmware_report() {
  const host = document.getElementById("host").value;
  const outputDiv = document.getElementById("networkdataOutput");
  outputDiv.innerHTML = `<div class="processing">Processing...</div>`;
  const url = `/bmo/oneview/firmware_compliance_report/${host}`;
  const response = await fetch(url, { method: "POST" });
  const data = await response.json();

  outputDiv.innerHTML = `<h3> Firmware Compliance Report for ${host} </h3>`;
  if (data && data.ReportFile) {
    // outputDiv.innerHTML += `<p>${JSON.stringify(data, null, 2)}</p>`;
    outputDiv.innerHTML += `<p>Report generated successfully. Loading report...</p>`;
    const response = await fetch(data.ReportFile);
    const htmlContent = await response.text();
    outputDiv.innerHTML += htmlContent;
    } else {
    outputDiv.innerHTML += `<p style="color: red;">${JSON.stringify(data, null, 2)}</p>`;
    }
}

async function fetchData(endpoint) {
  const outputDiv = document.getElementById("networkdataOutput");
  outputDiv.innerHTML = `<div class="processing">Processing...</div>`;
  const response = await fetch(endpoint);
  outputDiv.innerHTML = "";
  if (!response.ok) {
    const errorDetail = await response.json();
    outputDiv.innerHTML = `<pre style="color: red;">${JSON.stringify(errorDetail, null, 2)}</pre>`;
  } else {
    const data = await response.json();
    outputDiv.innerHTML = `
        <button id="copyButton">Copy</button>
        <button id="clearButton">Clear</button>
        <pre>${JSON.stringify(data, null, 2)}</pre>
        `;
    document.getElementById("clearButton").addEventListener("click", () => {
      outputDiv.innerHTML = "";
    });
    document.getElementById("copyButton").addEventListener("click", () => {
      navigator.clipboard
        .writeText(JSON.stringify(data, null, 2))
        .then(() => {
          alert("Copied to clipboard");
        })
        .catch((err) => {
          alert("Failed to copy: ", err);
        });
    });
    return data;
  }
}

async function checkStatus() {
  const buildid = document.getElementById("buildId").value;
  const url = `/builds/status/${buildid}`;
  console.log(url);
  const outputDiv = document.getElementById("outputContent3");
  const response = await fetch(url);
  if (!response.ok) {
    const errorDetail = await response.body();
    outputDiv.innerHTML += `<p style="color: red;">Error: ${errorDetail}</p>`;
  } else {
    const data = await response.json();
    outputDiv.innerHTML += `
        <pre><b>${JSON.stringify(data, null, 2)}<b></pre>
        `;
  }
}


async function myrequests(day) {
  url = `/builds/by/${username}/${day === 0 ? "today" : "lastweek"}`;
  // const url = `/builds/by/${username}`;
  const response = await fetch(url);
  // showSection("content");
  current_time = new Date().toLocaleString();
  const outputDiv = document.getElementById("myrequestsOutput");
  if (response.status === 404) {
    outputDiv.innerHTML = `<p style="color: red;"><b>No Request Found today</b></p>`;
    return;
  }
  const data = await response.json();
  outputDiv.innerHTML = `<p><b>Last updated: ${current_time}</b></p>`;
  const table = document.createElement("table");
  table.id = "bmo-data-table";
  table.style.borderRadius = "10px";
  table.innerHTML = `
    <thead>
      <tr>
        <th></th>
        <th>Host Name</th>
        <th>Build Type</th>
        <th>Build ID</th>
        <th>Status</th>
        <th>Time</th>
        <th>Requestor</th>
        <th>Log</th>
      </tr>
    </thead>
    <tbody></tbody>
    `;
  outputDiv.appendChild(table);
  const tableBody = document.querySelector("#bmo-data-table tbody");
  for (const item of data) {
    const row = document.createElement("tr");
    if (item.status === "QUEUED") {
      // document.documentElement.style.setProperty('--blinking-circle-color', 'blue');
      // document.documentElement.style.setProperty('--blinking-circle-animation', 'none');
      row.innerHTML += `
      <td><div id="solid-blue-circle"></div></td>
      `;
    }
    if (item.status === "PROCESSING") {
      row.innerHTML += `
      <td><div id="blinking-green-circle"></div></td>
      `;
    }
    if (item.status === "COMPLETE") {
      row.innerHTML += `
      <td><div id="solid-green-circle"></div></td>
      `;
    }
    if (item.status === "ERROR" || item.status === "ABORTED" || item.status === "ABORTING") {
      row.innerHTML += `
      <td><div id="solid-red-circle"></div></td>
      `;
    }
    row.innerHTML += `
      <td>${item.host}</td>
      <td>${item.build_type}</td>
      <td>${item.build_id}</td>
      <td>${item.status}</td>
      <td>${item.time}</td>
      <td>${item.requestor.requestor_id}</td>
      <td><button onclick="handleLogClick('${item.metadata.logfile}')">View Log</button></td>
    `;
    // <td><a href="${item.metadata.logfile}" target="_blank">View Log</a></td>
    tableBody.appendChild(row);
  }
}

function handleLogClick(logfileUrl) {
  console.log("Log file URL:", logfileUrl);
  // You can add your custom logic here, e.g., open in new tab, fetch content, etc.
  // Example: window.open(logfileUrl, '_blank');

  const viewerUrl = `log-viewer.html?url=${encodeURIComponent(logfileUrl)}`;
  window.open(viewerUrl, '_blank');

}


function adminBuildsTest() {
  const outputDiv = document.getElementById("adminservicesOutput");
  const myHeaders = new Headers();

  myHeaders.append("Authorization", `Basic ${authkey}`);

  const requestOptions = {
    method: "POST",
    headers: myHeaders,
    redirect: "follow"
  };

  fetch("/admin/builds/test", requestOptions)
    .then((response) => response.text())
    .then((result) => {
      outputDiv.innerHTML = `<pre>${result}</pre>`;
    })
    .catch((error) => {
      console.error("Error:", error);
      outputDiv.innerHTML = `<p style="color: red;">Error: ${error.message}</p>`;
    });

}


// Generanl /build endpoint call function
async function sendBuildRequest(endpoint, payload, outputDiv) {
  const url = endpoint;
  const requestOptions = {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Basic ${authkey}`
    },
    body: JSON.stringify(payload)
  };

  try {
    const response = await fetch(url, requestOptions);
    const data = await response.json();
    outputDiv.innerHTML += `
    <h3 style="color: gray;"><li>Build request for Host: <b>${payload.host}</b></li></h3>
    <pre>${JSON.stringify(payload, null, 2)}</pre>
  `;
    if (!response.ok) {
      outputDiv.innerHTML += `
      <h4 style="color: red;">Response: Failed to submit with response below</h4>
      <pre>${JSON.stringify(data, null, 2)}</pre>
    `;
    }
    else {
      outputDiv.innerHTML += `
      <h4 style="color: green;">Response: Submitted successfully</h4>
      <pre>${JSON.stringify(data, null, 2)}</pre>
    `;
    }
  } catch (error) {
    console.error("Error:", error);
    outputDiv.innerHTML += `<p style="color: red;">Error: ${error.message}</p>`;
  }
}


// All builds
let validHosts = [];

// LINUX BUILDS

// Attach event listeners to update JSON output dynamically

linux_payload = {
  host: "",
  os: "",
  attributes: {
    role: "",
    data_raid: ""
  },
  deploy_only: false,
  override: {}
}

document.getElementById('host_linux').addEventListener('input', updateLinuxJsonpayload);
document.getElementById('os_linux').addEventListener('change', updateLinuxJsonpayload);
document.getElementById('role_linux').addEventListener('change', updateLinuxJsonpayload);
document.getElementById('data_raid_linux').addEventListener('change', updateLinuxJsonpayload);
document.querySelectorAll('input[name="deploy_only_linux"]').forEach(radio => {
  radio.addEventListener('change', updateLinuxJsonpayload);
});

function updateLinuxJsonpayload() {
  const host = document.getElementById('host_linux').value;
  const hostInput = document.getElementById('host_linux').value;
  const overrideCheckbox = document.getElementById('overrideCheckbox');

  const os = document.getElementById('os_linux').value;
  if (os && !hostInput.includes(',')) {
    const overrideKeySelect = document.getElementById('overrideKey');
    const macOption = overrideKeySelect.querySelector('option[value="mac"]');
    if (macOption) {
      macOption.remove();
    }
  } else {
    overrideCheckbox.disabled = false;
  }
  const role = document.getElementById('role_linux').value;
  const dataRaid = document.getElementById('data_raid_linux').value;
  const deployOnly = document.querySelector('input[name="deploy_only_linux"]:checked').value === 'true';
  const overrideKey = document.getElementById('overrideKey').value;
  const overrideValue = document.getElementById('overrideValue').value;

  linux_payload.host = host;
  linux_payload.os = os;
  linux_payload.attributes.role = role;
  linux_payload.attributes.data_raid = dataRaid;
  linux_payload.deploy_only = deployOnly;

  if (overrideKey && overrideValue) {
    linux_payload.override[overrideKey] = overrideValue;
  }

  validHosts = [linux_payload];
  if (host.includes(',')) {
    const hosts = host.split(',').map(h => h.trim());
    if (hosts.length > 1) {
      const jsonOutputs = hosts.map(h => {
        const payload = { ...linux_payload };
        payload.host = h;
        return payload;
      });
      document.getElementById('jsonOutput_linux').value = JSON.stringify(jsonOutputs, null, 2);
      validHosts = jsonOutputs;
      return;
    }
  }
  document.getElementById('jsonOutput_linux').value = JSON.stringify(linux_payload, null, 2);
}

function toggleOverride() {
  const overrideYesBlock = document.getElementById('overrideYesBlock');
  overrideYesBlock.style.display = document.getElementById('overrideCheckbox').checked ? 'block' : 'none';
}

function addOverride() {
  const key = document.getElementById('overrideKey').value;
  const value = document.getElementById('overrideValue').value;

  if (key === "mac") {
    const macRegex = /^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$/;
    if (!macRegex.test(value)) {
      alert('Invalid MAC address format. Provide a valid MAC address like 11:22:33:44:55:66');
      return;
    }
  }
  if (key === "netmask" || key === "gateway") {
    const ipRegex = /^(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/;
    if (!ipRegex.test(value)) {
      alert('Invalid IP address format. Provide a valid IP address like 192.168.1.1');
      return;
    }
  }

  if (Array.isArray(validHosts)) {
    validHosts.forEach(item => {
      item.override = item.override || {};
      item.override[key] = value;
    });
  } else {
    parsedPayload = validHosts[0];
    parsedPayload.override = parsedPayload.override || {};
    parsedPayload.override[key] = value;
  }
  document.getElementById('jsonOutput_linux').value = JSON.stringify(validHosts, null, 2);
  document.getElementById('overrideKey').value = "";
  document.getElementById('overrideValue').value = "";

}

async function startLinuxBuild() {
  const endpoint = "/builds/linux";
  const outputDiv = document.getElementById("linuxOutput");
  outputDiv.innerHTML = ""; // Clear previous output
  const hostInput = document.getElementById('host_linux').value;
  if (hostInput.trim() === "") {
    alert("Please Provide hostname or hostnames");
    return;
  }
  const osInput = document.getElementById('os_linux').value;
  if (osInput.trim() === "") {
    alert("Please select an OS.");
    return;
  }
  const startLinuxBuildButton = document.getElementById("startLinuxBuild");
  startLinuxBuildButton.disabled = true;
  startLinuxBuildButton.innerText = "Processing...";
  startLinuxBuildButton.style.backgroundColor = "lightgreen";
  startLinuxBuildButton.style.animation = "blinking 1s infinite";

  if (validHosts.length === 0) {
    validHosts = document.getElementById('jsonOutput_linux').value
    console.log(validHosts);
    if (typeof validHosts === 'string') {
      try {
        validHosts = JSON.parse(validHosts);
        validHosts = Array.isArray(validHosts) ? validHosts : [validHosts];
      } catch (error) {
        console.error("Invalid JSON format:", error);
        alert("Invalid JSON format in the output. Please check your input.");
        return;
      }
    }
  }

  if (validHosts.length > 0) {
    await Promise.all(
      validHosts.map(async (payload) => {
        await sendBuildRequest(endpoint, payload, outputDiv);
      })
    );
  }

  outputDiv.innerHTML += `<hr>`;
  startLinuxBuildButton.innerText = "Build Job Submitted!";
  startLinuxBuildButton.style.backgroundColor = "black";
  startLinuxBuildButton.style.animation = "none";
  validHosts = [];
  setTimeout(() => {
    startLinuxBuildButton.innerText = "Start Build";
    startLinuxBuildButton.style.backgroundColor = "";
    startLinuxBuildButton.disabled = false;
  }, 10000);
}


// esxi build

esxi_payload = {
  host: "",
  os: "",
  attributes: {
    vlan: "3020"
  },
  deploy_only: false,
  override: {}
}

document.getElementById('host_esxi').addEventListener('input', updateEsxiJsonpayload);
document.getElementById('os_esxi').addEventListener('change', updateEsxiJsonpayload);
document.getElementById('vlan_esxi').addEventListener('input', updateEsxiJsonpayload);
document.querySelectorAll('input[name="deploy_only_esxi"]').forEach(radio => {
  radio.addEventListener('change', updateEsxiJsonpayload);
});

function updateEsxiJsonpayload() {
  const host = document.getElementById('host_esxi').value;
  const os = document.getElementById('os_esxi').value;
  const vlan = document.getElementById('vlan_esxi').value;
  const deployOnlyTrue = document.getElementById('deploy_only_true_esxi').checked === true;
  const deployOnlyInput = deployOnlyTrue || false;

  esxi_payload.host = host;
  esxi_payload.os = os;
  esxi_payload.attributes.vlan = vlan;
  esxi_payload.deploy_only = deployOnlyInput;
  validHosts = [esxi_payload];
  if (host.includes(',')) {
    const hosts = host.split(',').map(h => h.trim());
    if (hosts.length > 1) {
      const jsonOutputs = hosts.map(h => {
        const payload = { ...esxi_payload };
        payload.host = h;
        return payload;
      });
      document.getElementById('jsonOutput_esxi').value = JSON.stringify(jsonOutputs, null, 2);
      validHosts = jsonOutputs;
      return;
    }
  }
  document.getElementById('jsonOutput_esxi').value = JSON.stringify(esxi_payload, null, 2);

}

async function startEsxiBuild() {
  const endpoint = "/builds/esxi";
  const outputDiv = document.getElementById("esxiOutput");
  outputDiv.innerHTML = ""; // Clear previous output
  const hostInput = document.getElementById('host_esxi').value;
  if (hostInput.trim() === "") {
    alert("Please Provide hostname or hostnames");
    return;
  }
  const osInput = document.getElementById('os_esxi').value;
  if (osInput.trim() === "") {
    alert("Please select an OS.");
    return;
  }

  const startEsxiBuildButton = document.getElementById("startEsxiBuild");
  startEsxiBuildButton.disabled = true;
  startEsxiBuildButton.innerText = "Processing...";
  startEsxiBuildButton.style.backgroundColor = "lightgreen";
  startEsxiBuildButton.style.animation = "blinking 1s infinite";

  if (validHosts.length === 0) {
    validHosts = document.getElementById('jsonOutput_esxi').value
    console.log(validHosts);
    if (typeof validHosts === 'string') {
      try {
        validHosts = JSON.parse(validHosts);
        validHosts = Array.isArray(validHosts) ? validHosts : [validHosts];
      } catch (error) {
        console.error("Invalid JSON format:", error);
        alert("Invalid JSON format in the output. Please check your input.");
        return;
      }
    }
  }

  if (validHosts.length > 0) {
    await Promise.all(
      validHosts.map(async (payload) => {
        await sendBuildRequest(endpoint, payload, outputDiv);
      })
    );
  }

  outputDiv.innerHTML += `<hr>`;
  startEsxiBuildButton.innerText = "Build Job Submitted!";
  startEsxiBuildButton.style.backgroundColor = "black";
  startEsxiBuildButton.style.animation = "none";
  validHosts = [];
  setTimeout(() => {
    startEsxiBuildButton.innerText = "Start Build";
    startEsxiBuildButton.style.backgroundColor = "";
    startEsxiBuildButton.disabled = false;
  }, 10000);
}


// windows build

windows_payload = {
  host: "",
  os: "",
  attributes: {
    env: "",
    computerdomain: "",
    chef: true
  },
  deploy_only: false,
}

document.getElementById('host_windows').addEventListener('input', updateWindowsJsonpayload);
document.getElementById('os_windows').addEventListener('change', updateWindowsJsonpayload);
document.getElementById('environment_windows').addEventListener('input', updateWindowsJsonpayload);
document.getElementById('computerdomain_windows').addEventListener('input', updateWindowsJsonpayload);
document.querySelectorAll('input[name="deploy_only_windows"]').forEach(radio => {
  radio.addEventListener('change', updateWindowsJsonpayload);
});
document.querySelectorAll('input[name="chef_windows"]').forEach(radio => {
  radio.addEventListener('change', updateWindowsJsonpayload);
});

async function updateWindowsJsonpayload() {
  const host = document.getElementById('host_windows').value;
  const os = document.getElementById('os_windows').value;
  const environment = document.getElementById('environment_windows').value;
  const computerdomain = document.getElementById('computerdomain_windows').value;
  const deployOnlyTrue = document.getElementById('deploy_only_true_windows').checked === true;
  const cheftrue = document.getElementById('chef_true_windows').checked === true;
  const deployOnlyInput = deployOnlyTrue || false;
  const chef = cheftrue || false;

  windows_payload.host = host;
  windows_payload.os = os;
  windows_payload.attributes.env = environment;
  windows_payload.attributes.computerdomain = computerdomain;
  windows_payload.attributes.chef = chef; // Set chef attribute based on checkbox
  windows_payload.deploy_only = deployOnlyInput;
  validHosts = [windows_payload];
  if (host.includes(',')) {
    const hosts = host.split(',').map(h => h.trim());
    if (hosts.length > 1) {
      const jsonOutputs = hosts.map(h => {
        const payload = { ...windows_payload };
        payload.host = h;
        return payload;
      });
      document.getElementById('jsonOutput_windows').value = JSON.stringify(jsonOutputs, null, 2);
      validHosts = jsonOutputs;
      return;
    }
  }
  document.getElementById('jsonOutput_windows').value = JSON.stringify(windows_payload, null, 2);
}

async function addextraAttr() {
  const key = document.getElementById('attrKey').value;
  const value = document.getElementById('attrValue').value;

  if (Array.isArray(validHosts)) {
    validHosts.forEach(item => {
      console.log(item);
      const currentAttributes = item.attributes
      item.attributes = { ...currentAttributes, [key]: value };
    });
  } else {
    const item = validHosts[0];
    const currentAttributes = item.attributes
    item.attributes = { ...currentAttributes, [key]: value };
  }

  document.getElementById('jsonOutput_windows').value = JSON.stringify(validHosts, null, 2);
  document.getElementById('attrKey').value = "";
  document.getElementById('attrValue').value = "";
}

async function startWindowsBuild() {
  const endpoint = "/builds/windows";
  const outputDiv = document.getElementById("windowsOutput");
  outputDiv.innerHTML = ""; // Clear previous output
  const hostInput = document.getElementById('host_windows').value;
  if (hostInput.trim() === "") {
    alert("Please Provide hostname or hostnames");
    return;
  }
  const os = document.getElementById('os_windows').value;
  if (os.trim() === "") {
    alert("Please select a Windows OS");
    return;
  }
  const environment = document.getElementById('environment_windows').value;
  if (environment.trim() === "") {
    alert("Please select an environment");
    return;
  }
  // const computerdomain = document.getElementById('computerdomain_windows').value;
  // const deployOnlyTrue = document.querySelector('input[name="deploy_only_windows"]:checked').value;
  // const deployOnlyInput = deployOnlyTrue === "true";

  const startWindowsBuildButton = document.getElementById("startWindowsBuild");
  startWindowsBuildButton.disabled = true;
  startWindowsBuildButton.innerText = "Processing...";
  startWindowsBuildButton.style.backgroundColor = "lightgreen";
  startWindowsBuildButton.style.animation = "blinking 1s infinite";

  if (validHosts.length === 0) {
    validHosts = document.getElementById('jsonOutput_windows').value
    console.log(validHosts);
    if (typeof validHosts === 'string') {
      try {
        validHosts = JSON.parse(validHosts);
        validHosts = Array.isArray(validHosts) ? validHosts : [validHosts];
      } catch (error) {
        console.error("Invalid JSON format:", error);
        alert("Invalid JSON format in the output. Please check your input.");
        return;
      }
    }
  }
  if (validHosts.length > 0) {
    await Promise.all(
      validHosts.map(async (payload) => {
        await sendBuildRequest(endpoint, payload, outputDiv);
      })
    );
  }


  outputDiv.innerHTML += `<hr>`;
  startWindowsBuildButton.innerText = "Build Job Submitted!";
  startWindowsBuildButton.style.backgroundColor = "black";
  startWindowsBuildButton.style.animation = "none";

  setTimeout(() => {
    startWindowsBuildButton.innerText = "Start Build";
    startWindowsBuildButton.style.backgroundColor = "";
    startWindowsBuildButton.disabled = false;
    validHosts = [];
  }, 10000);
}


// File Upload Section

document.getElementById('esxiIsoUploadForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  outputDiv = document.getElementById('esxiIsoOutput');
  const formData = new FormData();
  const fileInput = document.getElementById('esxiIsoFile');
  formData.append('file', fileInput.files[0]);
  if (!fileInput.files.length) {
    alert('Please select a file to upload.');
    return;
  }

  const fileName = fileInput.files[0].name;
  const fileExtension = fileName.split('.').pop().toLowerCase();
  if (fileExtension !== 'iso') {
    alert('Only ISO files are allowed.');
    return;
  }
  console.log('File to upload:', fileName);
  console.log(authkey);
  try {
    outputDiv.innerHTML = `<div class="processing">Uploading ${fileName}...</div>`;
    const response = await fetch('/bmo/upload', {
      method: 'POST',
      headers: {
        "Authorization": `Basic ${authkey}`
      },
      body: formData
    });

    if (response.ok) {
      outputDiv.innerHTML = `<div class="success">File ${fileName} uploaded successfully!</div>`;
      // alert(`${fileName} uploaded successfully!`);
    } else {
      outputDiv.innerHTML = `<div class="error">Failed to upload file ${fileName}. Status: ${response.status}</div>`;
      // alert(`Failed to upload file ${fileName}`);
    }
  } catch (error) {
    console.error('Error:', error);
    alert('An error occurred while uploading the file.');
  }
});


/// Baseline HPE SPP
async function baseline_hp_spp() {
  endpoint = "/baseline/hp/spp";
  const outputDiv = document.getElementById("baselinehpsppOutput");
  outputDiv.innerHTML = ""; // Clear previous output
  const hostInput = document.getElementById('host_hp_spp').value;
  if (hostInput.trim() !== "") {
    hostsList = hostInput
      .split(",")
      .map((host) => host.trim())
      .filter((host) => host !== "");
    eskmFileInput.value = "";
  }
  if (hostInput.trim() === "") {
    alert(
      "Please enter a server/hostname or upload a file with server names each on a new line."
    );
    return;
  }

  const startSPPButton = document.getElementById("startSPP");
  startSPPButton.disabled = true;
  startSPPButton.innerText = "Processing...";
  startSPPButton.style.backgroundColor = "lightgreen";
  startSPPButton.style.animation = "blinking 1s infinite";
  const promises = hostsList.map(async (host) => {
    sendBuildRequest(endpoint, { host: host }, outputDiv)
  });
  await Promise.all(promises);

  // outputDiv.innerHTML += `<hr>`;
  startSPPButton.innerText = "SPP Job Submitted!";
  startSPPButton.style.backgroundColor = "black";
  startSPPButton.style.animation = "none";

  setTimeout(() => {
    startSPPButton.innerText = "Start SPP";
    startSPPButton.style.backgroundColor = "";
    startSPPButton.disabled = false;
    validHosts = [];
  }, 10000);
}

