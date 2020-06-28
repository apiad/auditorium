/**
 * A plugin which enables rendering of math equations inside
 * of reveal.js slides. Essentially a thin wrapper for MathJax 3
 *
 * @author Hakim El Hattab
 * @author Gerhard Burger
 */
var RevealMath3 = window.RevealMath3 || (function(){

	var options = Reveal.getConfig().math3 || {};
	var mathjax = options.mathjax || 'https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js';
	var url = mathjax;

	var defaultOptions = {
		tex: {
			// add this ugly deli,iter to avoid conflict with reveal and conflicts with $ symbol in html
			inlineMath: [ [ '$$$', '$$$' ], [ '\\(', '\\)' ]  ],
			tags: 'ams'
		},
		options: {
			skipHtmlTags: [ 'script', 'noscript', 'style', 'textarea', 'pre' ]
		},
		startup: {
			ready: () => {
      			MathJax.startup.defaultReady();
      			MathJax.startup.promise.then(() => {
      				Reveal.layout();
      			});
    		}
		}
	};

	function defaults( options, defaultOptions ) {

		for ( var i in defaultOptions ) {
			if ( !options.hasOwnProperty( i ) ) {
				options[i] = defaultOptions[i];
			}
		}

	}

	function loadScript( url, callback ) {

		var script = document.createElement( 'script' );
		script.type = "text/javascript"
		script.id = "MathJax-script"
		script.src = url;
		script.async = true

		// Wrapper for callback to make sure it only fires once
		var finish = function() {
			if( typeof callback === 'function' ) {
				callback.call();
				callback = null;
			}
		}
		script.onload = finish;

		document.head.appendChild( script );


	}

	return {
		init: function() {

			defaults( options, defaultOptions );
			defaults( options.tex, defaultOptions.tex );
			defaults( options.options, defaultOptions.options);
			defaults( options.startup, defaultOptions.startup );
			options.mathjax = null;
			window.MathJax = options;

			loadScript( url, function() {
				// Reprocess equations in slides when they turn visible
				Reveal.addEventListener( 'slidechanged', function( event ) {
					MathJax.typeset();
				} );
			} );

		}
	}

})();

Reveal.registerPlugin( 'math3', RevealMath3 );