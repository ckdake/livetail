$(document).ready(function() {

	function start() {
		$("#start").hide();
		refreshID = setInterval(function() {
			$.get("/records" + cluster + filter, {}, function(data) {
					$("#tail").prepend(data);	
				}
			);
		}, 1000);
		$("#stop").show();
	};

	setInterval(function() {
		$.get("/ping");
	}, 60000);

	setTimeout(function() { $("#closeme").hide() }, 10000);

	var refreshID;
	var cluster = "?";
	var filter = "/";

	$("#stop").hide();
	$("#applyfilter").hide();

	$("#cluster").change(function() {
		cluster = "?" + $("#cluster option:selected").val();
		$("#tail").text('');
		clearInterval(refreshID);
		start();

	});

	$("#applyfilter").click(function() {
		$("#applyfilter").hide();
		filter = "/" + $("#filter").val();
		$("#tail").text('');
                clearInterval(refreshID);
                start();
	});

	$("#filter").click(function() {
		$("#applyfilter").show();
	});

	$("#start").click(function() {
		start();
	});

	$("#stop").click(function() {
		$("#start").show();
		$("#stop").hide();
		clearInterval(refreshID);
	});

        $("#clear").click(function() {
                $("#tail").text('');
        });

	$("#closer").click(function() {
		$("#closeme").hide();
	});

});
