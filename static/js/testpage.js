// This script updates the status of the buttons on page load and every 1 second

function updatePage(data) {
	for(var index=0; index < data.length; index++){
		var object = data[index];
		
		var btnid = 'btn_' + object['id'];

		if ('limitsensoropen' in object['status']) {
			if (object['status']['limitsensoropen'] == 0) { 
				document.getElementById(btnid+'_limitsensoropen').className = "btn btn-secondary shadow";
			} else {
				document.getElementById(btnid+'_limitsensoropen').className = "btn btn-primary shadow";
			};
		}
		if ('limitsensorclosed' in object['status']) {
			if (object['status']['limitsensorclosed'] == 0) { 
				document.getElementById(btnid+'_limitsensorclosed').className = "btn btn-secondary shadow";
			} else {
				document.getElementById(btnid+'_limitsensorclosed').className = "btn btn-primary shadow";
			};
		}


	};
};

function setupListeners(data) {
	for(var index=0; index < data.length; index++){
		(function (){

			var object = data[index];

			var btnid = 'btn_' + object['id'];
			var keyname = object['keyname'];
		
			if ('doorbutton' in object['command']) {
				document.getElementById(btnid+'_doorbutton').addEventListener("click", function() {
					req = $.ajax({
						url : '/test',
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
			}
			if ('limitsensorclosed' in object['status']) {
					document.getElementById(btnid+'_limitsensorclosed').addEventListener("click", function() {
						req = $.ajax({
							url : '/test',
							type : 'POST',
							data : { 'keyname' : keyname,
									 'status' : 'limitsensorclosed' }
						});
						
						req.done(function(data) {
							if (data.result == 'success') {
								$('#'+btnid+'_limitsensorclosed').fadeOut(100).fadeIn(1000);
							} else {
								alert('Error sending data.');
							};
						});
					});
				}; 
				if ('limitsensoropen' in object['status']) {
					document.getElementById(btnid+'_limitsensoropen').addEventListener("click", function() {
						req = $.ajax({
							url : '/test',
							type : 'POST',
							data : { 'keyname' : keyname,
									 'status' : 'limitsensoropen' }
						});
						
						req.done(function(data) {
							if (data.result == 'success') {
								$('#'+btnid+'_limitsensoropen').fadeOut(100).fadeIn(1000);
							} else {
								alert('Error sending data.');
							};
						});
					});
				}; 

				
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