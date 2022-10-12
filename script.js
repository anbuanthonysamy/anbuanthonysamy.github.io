function clickListener(event){
	event.preventDefault();
	
	let emailInput = document.querySelector('#email');
	let messageInput = document.querySelector('#message');

	let emailText = emailInput.value;
	let messageText = messageInput.value;

	// console.log('email:', emailText, 'message:', messageText);

	if(emailValidate(emailText) !== true){
		alert('The email address must contain @');
		return false;
	}

	// alert('Thanks for your message');
}

function emailValidate(email){
	if(email.includes('@')){
		return true;
	} else {
		return false;
	}
}

let submitButton = document.querySelector('#submit-button');
submitButton.addEventListener('click', clickListener);
