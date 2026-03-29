var overlayPart = "_pane_overlay";
var distributionID = 0;
var links = {};
var DEBUG = false;

function goToHome() {
    var goToHomeForm = document.createElement('FORM');
    goToHomeForm.method = 'get';
    goToHomeForm.action = 'Home';
    goToHomeForm.id = 'goToHomeForm';
    document.body.appendChild(goToHomeForm);
    goToHomeForm.submit();
}

function loadLink(key, element) {
    change(links[key], element);
    $('.selectpicker').selectpicker('val', key);
}

function adminChange(url, element) {
    $("#specialMenu").empty();
    change(url, element);
}

function doLogout() {
    window.location.href = "Logout";
}

function appendCSRFNonce(url) {
    if (csrf_nonce === "") {
        consoleLog("Error: csrf_nonce empty");
        return url;
    }
    if (url.indexOf("?") !== -1) {
        return url + "&CSRF_NONCE=" + csrf_nonce;
    } else {
        return url + "?CSRF_NONCE=" + csrf_nonce;
    }    
}

function change(url, element) {
    consoleLog("change called to url: " + url);
    url = appendCSRFNonce(url);
    if (element === "specialMenu") {
        //clean event handlers from older links
        $("a").unbind();
        $("#specialMenu").empty();
        //reload nav dropdown
        if ($('.selectpicker') !== null && url.indexOf("VServersKVM") === -1) {
            $('.selectpicker').selectpicker('deselectAll');
            $('.selectpicker').selectpicker('render');
        }
    }
    showOverlayAndCreateIfNotExist(element);
    $("#" + element).load(url, function() {
        hideOverlayIfExistForDiv(element);
    });
}

function showLoginIf403(e) {
    if (e.status === 403) {
        $('page').innerHTML = e.responseText;
    }
}

function loadWithOverlayGet(url, divToUpdate) {
    consoleLog("loadWithOverlayGet called to url: " + url);
    url = appendCSRFNonce(url);
    showOverlayAndCreateIfNotExist(divToUpdate);
    $.ajax({
        url: url,
        success: function (data) {
            $('#' + divToUpdate).html(data);
            hideOverlayIfExistForDiv(divToUpdate);
        },
        failure: function (transport) {
            showLoginIf403(transport);
        }
    });
    return false;
}

function loadWithOverlayPost(url, divToUpdate, postParameters) {
    consoleLog("loadWithOverlayPost called to url: " + url);
    url = appendCSRFNonce(url);
    showOverlayAndCreateIfNotExist(divToUpdate);
    $.ajax({
        type: "POST",
        url: url,
        data: postParameters,
        success: function (data) {
            $("#" + divToUpdate).html(data);
            hideOverlayIfExistForDiv(divToUpdate);
        },
        failure: function (transport) {
            showLoginIf403(transport);
        }
    });
    return false;
}

function selectOptionValue(formObject, selectBoxName, optionValue) {
    var options = $("select[name='"+selectBoxName+"']");
    for (var i = 0; i <= options.length; i++) {
        if (options[i] !== undefined) {
            if (options[i].val() === optionValue) {
                options[i].selected = true;
            }
        }

    }
}

function changeBackupConfirmAction(classNameToHide, classIdToShow) {
    $$('div.' + classNameToHide).invoke('hide');
    $(classIdToShow).show();
}

function sendFormAndChange(formId, url, changeUrl, element) {
    url = appendCSRFNonce(url);
    var pars = $("#" + formId).serialize();
    showOverlayAndCreateIfNotExist('content');
    $.ajax({
        type: "POST",
        url: url,
        timeout: 600000,
        data: pars,
        success: function (data) {
            $('#content').html(data);
            change(changeUrl, element);
        },
        failure: function (transport) {
            showLoginIf403(transport);
        }
    });
    return false;
}

function sendForms(formIds, divToUpdate, url, type) {
    url = appendCSRFNonce(url);
    const pars = formIds.map(id => $("#" + id).serialize()).join('&');
    showOverlayAndCreateIfNotExist(divToUpdate);
    $.ajax({
        type: type === undefined ? "POST" : type,
        url: url,
        timeout: 600000,
        data: pars,
        success: function (data) {
            // fix for legacy application
            if(data.indexOf(`setHeaderLine('<span id="site_maintitle_category">Linux vServer</span>');`) !== -1) {
                $('#content').html(data);
            } else {
                $("#" + divToUpdate).html(data);
            }
            hideOverlayIfExistForDiv(divToUpdate);
        },
        failure: function (transport) {
            showLoginIf403(transport);
        }
    });
    return false;
}

function sendForm(formId, divToUpdate, url, type) {
    url = appendCSRFNonce(url);
    var pars = $("#" + formId).serialize();
    showOverlayAndCreateIfNotExist(divToUpdate);
    $.ajax({
        type: type === undefined ? "POST" : type,
        url: url,
        timeout: 600000,
        data: pars,
        success: function (data) {
            // fix for legacy application
            if(data.indexOf(`setHeaderLine('<span id="site_maintitle_category">Linux vServer</span>');`) !== -1) {
                $('#content').html(data);
            } else {
                $("#" + divToUpdate).html(data);
            }
            hideOverlayIfExistForDiv(divToUpdate);
        },
        failure: function (transport) {
            showLoginIf403(transport);
        }
    });
    return false;
}

function sendFormAndReloadSCP(formId, url) {
    url = appendCSRFNonce(url);
    var pars = $("#" + formId).serialize();
    showOverlayAndCreateIfNotExist('SCP');
    $.ajax({
        type: "POST",
        url: url,
        timeout: 600000,
        data: pars,
        success: function (data) {
            document.open();
            document.write(data);
            document.close();
            hideOverlayIfExistForDiv('SCP');
        },
        failure: function (transport) {
            showLoginIf403(transport);
        }
    });
    return false;
}

function sendFormWithUncheckedBoxesAsFalse(formId, divToUpdate, url) {
    consoleLog("sendFormWithUncheckedBoxesAsFalse");
    $("input[type=checkbox]").each(function () {
        var input = $(this);
        if (!this.checked) {
            var notCheckedBoxElement = document.createElement('input');
            notCheckedBoxElement.name = input.prop("name");
            notCheckedBoxElement.type = 'hidden';
            notCheckedBoxElement.value = 'false';
            $("#" + formId).append(notCheckedBoxElement);

        }
    });
    sendForm(formId, divToUpdate, url);
}

function isCheckBoxChecked(checkBoxId) {
    return $("#" + checkBoxId).is(':checked');
}

function elementExists(elementId) {
    if ($("#" + elementId).length) {
        return true;
    }
    return false;
}

function getFormElementValue(elementid, defaultValue) {
    if (elementExists(elementid)) {
        return $("#" + elementid).val();
    }
    return defaultValue;
}

function showOverlayAndCreateIfNotExist(divToUpdate) {
    $("#" + divToUpdate).empty();
    consoleLog("add overlay to div: " + divToUpdate);
    if ($("#" + divToUpdate + overlayPart) !== undefined) {
        $("body").removeClass("loadingoverlay");
        $("#" + divToUpdate + overlayPart).remove();
    }
    $("body").addClass("loadingoverlay");
    $("#SCP").append("<div id=\"" + divToUpdate + overlayPart + "\" class=\"overlay\"></div>");
}

function hideOverlayIfExistForDiv(divWithOverlay) {
    consoleLog("remove overlay from div: " + divWithOverlay);
    $("#" + divWithOverlay + overlayPart).remove();
    $("#" + divWithOverlay + overlayPart).remove();
    if ($(".overlay").length === 0) {
        $("body").removeClass("loadingoverlay");
    }
}

function createTabbedPane(update, page_urls, divToAdd) {
    $("#"+divToAdd).empty();
    for (var page_id in page_urls) {
        $("#"+divToAdd).append("<div id=\"" + page_id + "_update\" style=\"display: none;\" class=\"pane\"></div>");
        $('#' + page_id).click(function (event) {
            e = event.currentTarget;
            //alert("tabbed pane event: " + Event.element(e).id);
            for (var key in page_urls) {
                $("#" + key + update).hide();
                $("#" + key + update).empty();
                $("#" + key).parent().removeClass('active');
            }
            $("#" + e.id + update).empty();
            $("#" + e.id + update).show();
            showOverlayAndCreateIfNotExist(e.id+update);
            $("#" + e.id).parent().addClass('active');
            loadTabPage(e.id, page_urls[e.id], update);
        });
        if ($("#" + page_id).parent().hasClass('active')) {
            $("#" + page_id + update).empty();
            $("#" + page_id + update).show();
            showOverlayAndCreateIfNotExist(page_id+update);
            loadTabPage(page_id, page_urls[page_id], update);
        }
    }
}

function createNav(update, page_urls, pageToLoad) {
    //clean content
    $("#content").empty();
    for (var page_id in page_urls) {
        //create new Element
        $("#content").append("<div id=\"" + page_id + "_update\" style=\"display: none;\" class=\"pane\"></div>");
        $('#' + page_id).click(function (event) {
            e = event.currentTarget;
            for (var key in page_urls) {
                //alert("hide " + key+update);
                $("#" + key + update).hide();
                $("#" + key + update).empty();
                $("#" + key).removeClass('active');
            }
            $("#" + e.id + update).empty();
            $("#" + e.id + update).show();
            showOverlayAndCreateIfNotExist(e.id+update);
            $("#" + e.id).addClass("active");
            consoleLog("try to load URL for id " + e.id + ": " + page_urls[e.id] + " from " + page_urls);
            loadTabPage(e.id, page_urls[e.id], update);
        }
        );

        if (page_id === pageToLoad) {
            $("#" + page_id + update).empty();
            $("#" + page_id + update).show();
            showOverlayAndCreateIfNotExist(page_id+update);
            loadTabPage(page_id, page_urls[page_id], update);
        }
    }
}

function loadTabPage(pageId, url, updatePart) {
    consoleLog("loadTabPage called to url: " + url);
    url = appendCSRFNonce(url);
    $.ajax({
        url: url,
        success: function (data) {
            $("#" + pageId + updatePart).html(data);
            updateSiteTitle();
            hideOverlayIfExistForDiv(pageId+updatePart);
        },
        failure: function (transport) {
            showLoginIf403(transport);
        }
    });
}

function setHeaderLine(headerLineText) {
    setHeaderLine(headerLineText, '');
}

function setHeaderLine(headerLineText, subText) {
    if ($('#headerline') !== undefined) {
        if (headerLineText === undefined) {
            headerLineText = '';
        }
        if (subText === undefined) {
            subText = '';
        }
        $('#headerline').html(headerLineText + '&nbsp;<span>' + subText + '</span>');
    }
}

function toggleElement(elementToToggle, elementWithImage) {
    if (document.getElementById(elementToToggle).style.display === 'none') {
        document.getElementById(elementToToggle).style.display = 'block';
        $("#" + elementWithImage).removeClass('defaultExpand');
        $("#" + elementWithImage).addClass('defaultCollapse');
    } else {
        document.getElementById(elementToToggle).style.display = 'none';
        $("#" + elementWithImage).addClass('defaultExpand');
        $("#" + elementWithImage).removeClass('defaultCollapse');
    }
}

function toggleIPv6Button() {
    $('#addIPv6Button').hide();
    $('#removeIPv6Button').show();
}

function checkBox(id) {
    $('#' + id).prop('checked', true);
}

function genAdminPasswordAndInsert(id) {
    document.getElementById(id).value = generatePassword(25);
    document.getElementById(id).type = "input";
}

function genPasswordAndInsert(id, length) {
    document.getElementById(id).value = generatePassword(9);
    document.getElementById(id).type = "input";
}

function genWebServicePasswordAndInsert() {
    $('#webServicePassword').val(generatePassword(12));
}

function genRootPasswordAndInsert() {
    $('#newRootPassword').val(generatePassword(10));
}

// from: http://jquery-howto.blogspot.com/2009/10/javascript-jquery-password-generator.html
function generatePassword(length) {
    var iteration = 0;
    var password = "";
    var randomNumber;
    while (iteration < length) {
        randomNumber = (Math.floor((Math.random() * 100)) % 94) + 33;
        if ((randomNumber >= 33) && (randomNumber <= 47)) {
            continue;
        }
        if ((randomNumber >= 58) && (randomNumber <= 64)) {
            continue;
        }
        if ((randomNumber >= 91) && (randomNumber <= 96)) {
            continue;
        }
        if ((randomNumber >= 123) && (randomNumber <= 126)) {
            continue;
        }
        iteration++;
        password += String.fromCharCode(randomNumber);
    }
    return password;
}

function checkCheckbox(id, text) {
    if ($("#" + id).is(":checked")) {
        $("#" + id).addClass(id, "active");
        return false;
    }
    return true;
}

function goBackToDistribution() {
    $('#distribution').show();
    var fieldsets = document.getElementsByTagName('div');
    for (var i = 0; i < fieldsets.length; i++) {
        if (fieldsets[i].id.indexOf("distribution_") !== -1) {
            fieldsets[i].style.display = 'none';
        }
    }
    $('#distributionValue').empty();
    distributionID = 0;
    $('#step1').addClass('stepCurrent');
    $('#step1').removeClass('stepDone');
    $('#step2').addClass('stepToCome');
    $('#step2').removeClass('stepCurrent');
    $('#step2').removeClass('InstallStepDone');

}
function goToFlavour(selectedDistributionID, selectedDistributionAlias) {
    //var selectedDistributionID = $('input[name=selectedDistribution]:checked', '#selectDistribution').val();
    if (selectedDistributionID === 0) {
        consoleLog("could not find distribution");
        return;
    }

    distributionID = selectedDistributionID;

    $('#distribution').hide();

    $('#distribution_' + selectedDistributionID).show();

    $('#distributionValue').html(selectedDistributionAlias);

    $('#step1').addClass('stepDone');
    $('#step1').removeClass('stepCurrent');
    $('#step2').addClass('stepCurrent');
    $('#step2').removeClass('stepToCome');
    $('#step2').addClass('InstallStepDone');
}

function goBackToFlavour() {
    $('#distribution_' + distributionID).show();
    $('#partitioning').hide();
    $('#setupImageFormSelectedFlavour').val("");
    $('#flavourValue').empty();
    $('#step2').addClass('stepCurrent');
    $('#step2').removeClass('stepDone');
    $('#step3').addClass('stepToCome');
    $('#step3').removeClass('stepCurrent');
    $('#step3').removeClass('InstallStepDone');
}

function goToPartitioning(selectedFlavourID, selectedFlavourAlias) {
    //var selectedFlavourID = $('input[name=selectedFlavour]:checked', '#selectFlavour_' + distributionID).val();
    if (selectedFlavourID === 0) {
        consoleLog("could not find flavour");
        return;
    }

    $('#setupImageFormSelectedFlavour').val(selectedFlavourID);

    $('#distribution_' + distributionID).hide();

    $('#partitioning').show();

    $('#flavourValue').html(selectedFlavourAlias);

    $('#step2').addClass('stepDone');
    $('#step2').removeClass('stepCurrent');
    $('#step3').addClass('stepCurrent');
    $('#step3').removeClass('stepToCome');
    $('#step3').addClass('InstallStepDone');
}

function goBackToPartitioning() {
    $('#partitioning').show();
    $('#confirmation').hide();
    $('#setupImageFormSelectedPartitioning').val("");
    $('#partitioningValue').empty();
    $('#step3').addClass('stepCurrent');
    $('#step3').removeClass('stepDone');
    $('#step4').addClass('stepToCome');
    $('#step4').removeClass('stepCurrent');
    $('#step4').removeClass('InstallStepDone');
}

function goToEmail(selectedPartitionType) {
    //var selectedPartitionType = $('input[name=resizeImage]:checked', '#selectPartitioning').val();
    if (selectedPartitionType !== "true" && selectedPartitionType !== "false") {
        consoleLog("could not find selectedPartitionType");
        return;
    }

    if (selectedPartitionType === "true") {
        $('#partitioningValue').html($('#oneLargePartition').html());
    } else {
        $('#partitioningValue').html($('#smallPartition').html());
    }

    $('#setupImageFormSelectedPartitioning').val(selectedPartitionType);

    $('#partitioning').hide();
    $('#email').show();

    $('#step3').addClass('stepDone');
    $('#step3').removeClass('stepCurrent');
    $('#step4').addClass('stepCurrent');
    $('#step4').removeClass('stepToCome');
    $('#step4').addClass('InstallStepDone');
}

function goBackToEmail() {
    $('#email').show();
    $('#confirmation').hide();

    $('#emailValue').empty();

    $('#adminEMailClonedElement').remove();
    $('#resellerEMailClonedElement').remove();
    $('#endUserEMailClonedElement').remove();

    $('#step4').addClass('stepCurrent');
    $('#step4').removeClass('stepDone');
    $('#step5').addClass('stepToCome');
    $('#step5').removeClass('stepCurrent');
    $('#step5').removeClass('InstallStepDone');
}

function goToConfirmation(selectedPartitionType, selectedOptionText) {
    if (selectedPartitionType !== true && selectedPartitionType !== false) {
        consoleLog("could not find selectedPartitionType");
        return;
    }

    $('#partitioningValue').html(selectedOptionText);
    $('#hostNameValue').text($('#hostNameField').val() !== '' ? $('#hostNameField').val():
        $('#hostNameField').attr('placeholder'));
    $('#localeValue').text($('#selectedLocale').val());
    $('#timezoneValue').text($('#selectedTimeZone').val());

    const createUser = document.querySelector('#createUser').value;
    if (createUser === 'true') {
        $('#usernameValue').text($('#usernameField').val());
        $('#passwordValue').text($('#passwordField').val());
        $('#setupImageFormSelectedUsername').val($('#usernameField').val());
        $('#setupImageFormSelectedPassword').val($('#passwordField').val());
    }

    $('#sshKeyValue').text($('#selectedSSHKeys option:selected').map(function(){ return $(this)[0].text}).get().join(" "));
    $('#sshPasswordAuthentication').prop('checked', $('#activateSSHPassword').bootstrapSwitch('state'));
    $('#customScriptValue').val($('#customScriptField').val());

    $('#setupImageFormSelectedPartitioning').val(selectedPartitionType);
    $('#setupImageFormSelectedHostName').val($('#hostNameField').val());
    $('#setupImageFormSelectedLocale').val($('#selectedLocale').val());
    $('#setupImageFormSelectedTimezone').val($('#selectedTimeZone').val());
    $('#setupImageFormSelectedSSHKey').val($('#selectedSSHKeys option:selected').map(function(){ return $(this)[0].value}).get().join(" "));
    $('#setupImageFormSelectedSSHPasswordAuthentication').val($('#activateSSHPassword').bootstrapSwitch('state'));
    $('#setupImageFormSelectedCustomScript').val($('#customScriptField').val().replace(/\r\n/g, "\n"));
    $('#setupImageFormSelectedCustomScript').val(btoa($('#setupImageFormSelectedCustomScript').val()));

    $('#partitioning').hide();
    $('#confirmation').css('display','block');

    $('#step4').addClass('stepDone');
    $('#step4').removeClass('stepCurrent');
    $('#step5').addClass('stepCurrent');
    $('#step5').removeClass('stepToCome');
    $('#step5').addClass('InstallStepDone');
}

function getScreenshot(elementid, vserverid, contextpath) {
    if ($('#ScreenshotImage') !== null) {
        $('#ScreenshotImage').remove();
    }
    $("#" + elementid).append("<img id=\"ScreenshotImage\" class=\"img-responsive img-thumbnail\" src=\"" + contextpath + "/ScreenshotViewer?selectedVServerId=" + vserverid + "\"/>");
}

function jqide(id) {
    return id.replace(/(:|\.|\[|\]|,)/g, "\\$1");
}

function updateSiteTitle() {
    var SiteCategory = document.getElementById("site_maintitle_category");
    if (SiteCategory === null) {
        SiteCategory = "unknown";
    }
    var SitePagename = document.getElementById("site_maintitle_pagename");
    if (SitePagename === null) {
        SitePagename = "unknown";
    }

    if (SitePagename.length === 0 || SiteCategory === SitePagename) {
        document.title = "SCP - " + SiteCategory.innerHTML;
    } else {
        document.title = "SCP - " + SitePagename.innerHTML + " (" + SiteCategory.innerHTML + ")";
    }
}

function consoleLog(text) {
    if(DEBUG) {
        console.log(text);
    }
}

function extractSSHNameField(sshKey) {
    const splitted = sshKey.split(' ');
    if(splitted.length === 3) {
        return splitted[2]; // comment field
    }

    return '';
}

function markElementAsHasErrorAndAddErrorMessageIfNotValid(elementValid, item, errorMessage) {
    const errorMessageElement = $('#error-message');
    if (!elementValid) {
        const errorElement = createErrorFeedbackPanel(errorMessage);
        if (errorMessageElement.length) {
            errorMessageElement.html(errorElement);
        } else {
            item.prepend(errorElement);
        }
    }else{
        errorMessageElement.remove();
    }
    item.toggleClass('has-error', !elementValid);

}

function createErrorFeedbackPanel(errorMessage){
    return `<div class="row" id="error-message">
    <div class="col-lg-12">
        <div class = "panel panel-danger">
            <div class="panel-heading">
                <i class="fa fa-times-circle"></i>&nbsp;<fmt:message key="Control.hint.title" /><br>
            </div>
            <div class="panel-body">
                ${errorMessage}
            </div>
        </div>
    </div>
</div>`;
}

const scpCoreUrlApiPrefix = "/scp-core/api/v1/";

async function getAuthToken() {
    return fetch("/SCP/TokenServlet", {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json'
        }
    })
        .then(response => response.json())
        .then(data => 'Bearer ' + data.access_token);
}

async function getRefreshAuthToken() {
    return fetch("/SCP/TokenServlet", {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json'
        }
    })
        .then(response => response.json())
        .then(data => data.refresh_token);
}

class FileUpload {
    constructor(fileName, file, url) {
        this.fileName = fileName;
        this.file = file;
        this.url = url;
    }

    uploadId;
    uploadPartsArray;
    progressCallback;

    async upload(progressCallback) {
        this.progressCallback = progressCallback;
        progressCallback(0);
        this.uploadId = await this.createUpload();
        await this.uploadMultipartFileP();
        await this.finishUpload();
    }

    async uploadMultipartFileP() {
        const FILE_CHUNK_SIZE = 50000000; // 50MB
        const fileSize = this.file.size;
        const NUM_CHUNKS = Math.floor(fileSize / FILE_CHUNK_SIZE) + 1;
        let start, end, blob;
        this.uploadPartsArray = [];

        for (let index = 1; index < NUM_CHUNKS + 1; index++) {
            start = (index - 1)*FILE_CHUNK_SIZE;
            end = (index)*FILE_CHUNK_SIZE;
            blob = (index < NUM_CHUNKS) ? this.file.slice(start, end) : this.file.slice(start);

            let token = await getAuthToken();
            const response = await fetch(this.url + this.fileName + "/" + this.uploadId + "/parts/" + index, {
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': token
                }
            });
            const data = await response.json();
            let presignedUrl = data.url;

            const uploadResponse = await fetch(presignedUrl, {
                method: "PUT",
                body: blob
            });
            
            this.uploadPartsArray.push({
                ETag: uploadResponse.headers.get("ETag"),
                partNumber: index
            });            

            this.progressCallback(index / NUM_CHUNKS * 100);
        }
    }

    async finishUpload() {
        let token = await getAuthToken();
        await fetch(this.url + this.fileName + "/" + this.uploadId, {
            method: "PUT",
            headers: {
                'Content-Type': 'application/json',
                'Authorization': token
            },
            body: JSON.stringify(this.uploadPartsArray),
        });
    }

    async createUpload() {
        let token = await getAuthToken();
        return fetch(this.url + this.fileName, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': token
            }
        })
            .then((response) => {
                if (response.ok) {
                    return response.json();
                } else {
                    return Promise.reject(response);
                }
            })
            .then(data => data.uploadId);
    }
}

function copyToClipboard(text) {
    var dummy = document.createElement("textarea");
    document.body.appendChild(dummy);
    dummy.value = text;
    dummy.select();
    document.execCommand("copy");
    document.body.removeChild(dummy);
}

function waitUntilElementIsAvailable(selector) {
    return new Promise(resolve => {
        if (document.querySelector(selector)) {
            return resolve(document.querySelector(selector));
        }

        const observer = new MutationObserver(mutations => {
            if (document.querySelector(selector)) {
                observer.disconnect();
                resolve(document.querySelector(selector));
            }
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    });
}

function fetchAndParseCsv(csvUrl) {
    return fetch(csvUrl)
        .then(r => r.text())
        .then(text => {
            let parsedRows = d3.csvParseRows(text);
            let cols = parsedRows[0];
            return {
                columns: cols,
                rows: parsedRows.slice(1).map(row =>
                    Object.fromEntries(cols.map((c, i) => [c, row[i]]))
                )
            }
        });
}