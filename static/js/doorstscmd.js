// This script updates the status of the buttons on page load and every 1 second

function updatePage(data) {
	for(var index=0; index < data.length; index++){
		var object = data[index];
		
		var btnid = 'btn_' + object['id'];
		var btnimgid = 'btnimg_' + object['id'];
		var cardid = 'card_' + object['id'];
		var textid = 'text_' + object['id'];

		if ('limitsensoropen' in object['status']) {
			if ((object['status']['limitsensorclosed'] == 1)&&(object['status']['limitsensoropen'] == 0)) { 
				document.getElementById(btnid).className = "btn btn-success btn-block shadow";
				document.getElementById(btnimgid).src = imgfolder + "doorclosed.png";
				document.getElementById(cardid).className = "card bg-success shadow mx-auto";
				document.getElementById(textid).innerHTML = "CLOSED <i class=\"fas fa-lock\"></i>";
			} else if ((object['status']['limitsensorclosed'] == 0)&&(object['status']['limitsensoropen'] == 0)) {
				document.getElementById(btnid).className = "btn btn-warning btn-block shadow";
				document.getElementById(btnimgid).src = imgfolder + "dooropen.png";
				document.getElementById(cardid).className = "card bg-warning shadow mx-auto";
				document.getElementById(textid).innerHTML = "OPEN <i class=\"fas fa-lock-open\"></i>";
			} else {
				document.getElementById(btnid).className = "btn btn-danger btn-block shadow";
				document.getElementById(btnimgid).src = imgfolder + "dooropen.png";
				document.getElementById(cardid).className = "card bg-danger shadow mx-auto";
				document.getElementById(textid).innerHTML = "OPEN <i class=\"fas fa-lock-open\"></i>";
			};
		} else {
			if (object['status']['limitsensorclosed'] == 1) { 
				document.getElementById(btnid).className = "btn btn-success btn-block shadow";
				document.getElementById(btnimgid).src = imgfolder + "doorclosed.png";
				document.getElementById(cardid).className = "card bg-success shadow mx-auto";
				document.getElementById(textid).innerHTML = "CLOSED <i class=\"fas fa-lock\"></i>";
			} else {
				document.getElementById(btnid).className = "btn btn-danger btn-block shadow";
				document.getElementById(btnimgid).src = imgfolder + "dooropen.png";
				document.getElementById(cardid).className = "card bg-danger shadow mx-auto";
				document.getElementById(textid).innerHTML = "OPEN <i class=\"fas fa-lock-open\"></i>";
			};
		};
	};
};

function setupListeners(data) {
	for(var index=0; index < data.length; index++){
		(function (){

			var object = data[index];

			var btnid = 'btn_' + object['id'];
			var keyname = object['keyname'];
			var cmd = object['command'];
		
			document.getElementById(btnid).addEventListener("click", function() {
				req = $.ajax({
					url : '/button',
					type : 'POST',
					data : { 'keyname' : keyname,
							 'button' : 'doorbutton' }
				});
				
				req.done(function(data) {
					if (data.result == 'success') {
						$('#'+btnid).fadeOut(100).fadeIn(1000);
					} else {
						alert('Error sending button press.');
					};
				});
			});
		}()); // Required or else the listerners won't get created properly
	};
};

// Update page data
$(document).ready(function(){
    // Get Intial Dash Data
    req = $.ajax({
		url : '/status',
		type : 'GET'
    });
    req.done(function(data) {
        // Setup Initial Dash Data
		updatePage(data);
		setupListeners(data);
	});

	setInterval(function(){
		req = $.ajax({
			url : '/status',
			type : 'GET'
		});
		req.done(function(data) {
			// Setup Initial Dash Data
			updatePage(data);
		});
	}, 1000);
}); // End of Document Ready Function

