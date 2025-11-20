// Copyright (C) 2024, 2025 Oracle and/or its affiliates.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

document.addEventListener("DOMContentLoaded", function () {
  const closeBtn = document.getElementById("close-announcement");
  const banner = document.querySelector(".bd-header-announcement");

  if (banner) {
    banner.style.display = "none";
  }

  if (!sessionStorage.getItem("announcementClosed")) {
    if (banner) {
      banner.style.display = "block";
    }

    if (closeBtn) {
      closeBtn.addEventListener("click", function () {
        banner.style.display = "none";
        sessionStorage.setItem("announcementClosed", "true");
      });
    }
  }
});
