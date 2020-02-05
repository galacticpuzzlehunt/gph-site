$(function() {
  function toggle(open) {
    tray.css('transform', open ? 'none' : '');
  }
  var tray = $('.tray').mousedown(function(e) {
    if (e.target == tray[0]) {
      toggle(e.clientY < tray[0].offsetHeight - 20 &&
          e.clientY >= tray.children()[0].getBoundingClientRect().top);
      e.preventDefault();
    }
    e.stopPropagation();
  });
  var swipe = null;
  var nav = $('nav').swipe({
    fallbackToMouseEvents: false,
    preventDefaultEvents: false,
    swipeStatus: function(e, phase) {
      if (phase == 'start') {
        swipe = [e.touches[0].clientY, tray[0].style.transform];
        $('body').css('overflow', 'hidden');
        tray.css('transition', 'none');
      }
    },
  });
  $(document).mousedown(function(e) {
    toggle(false);
  }).swipe({
    excludedElements: 'a, label',
    fallbackToMouseEvents: false,
    preventDefaultEvents: false,
    swipeStatus: function(e, phase, direction) {
      if (swipe == null) {
        return;
      }
      switch (phase) {
        case 'move':
          var base = swipe[1] ? 0 : tray[0].offsetHeight;
          var total = e.touches[0].clientY - swipe[0] - base;
          if (total > 0) {
            total = Math.pow(total, 0.75);
          }
          tray.css('transform', 'translateY(' + total + 'px)');
        default:
          return;
        case 'end':
          if (direction == 'up') {
            toggle(false);
          } else if (direction == 'down') {
            toggle(true);
          }
          break;
        case 'cancel':
          if ($.contains($('.top-right-actions')[0], e.target)) {
            toggle(true);
          } else {
            toggle(swipe[1]);
          }
          break;
      }
      swipe = null;
      $('body').css('overflow', '');
      tray.css('transition', '');
    },
  });
});
